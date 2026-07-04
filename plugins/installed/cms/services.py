"""CMS services."""
# ruff: noqa: PLC0415 — model/hook imports are lazy (load-order safe).

from __future__ import annotations

import hashlib
import logging
import re

from django.utils import timezone

logger = logging.getLogger('morpheus.cms')


def get_live_page(slug: str):
    """Resolve a slug to a published Page (respects publish_at)."""
    from plugins.installed.cms.models import Page

    page = Page.objects.filter(slug=slug, state='published').first()
    if page is None:
        return None
    if page.publish_at and page.publish_at > timezone.now():
        return None
    return page


def _read_minutes(body: str) -> int:
    """Honest reading-time estimate: strip tags, count words, ~200 wpm."""
    words = len(re.sub(r'<[^>]+>', ' ', body or '').split())
    return max(1, round(words / 200))


def _str_list(value) -> list[str]:
    """Coerce a free-form ``page.metadata`` value into a clean ``list[str]``.

    author_same_as / citations are authored as raw JSON today, so a merchant
    can plausibly write a single URL as a scalar string. Passing that scalar
    on to the JSON-LD tag would ``list()``-explode it into one entry per
    character; coerce a bare string to a one-item list and drop anything that
    isn't a string/list so the Article schema stays valid.
    """
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    return []


def _journal_dict(page) -> dict:
    pub = page.publish_at or page.updated_at or page.created_at
    meta = page.metadata or {}
    # Cover image for OG + Article JSON-LD: explicit metadata first, else the
    # first <img> in the (already-sanitised) body.
    image = (meta.get('cover') or meta.get('image') or meta.get('og_image') or '').strip()
    if not image and page.body:
        m = re.search(r"""<img[^>]+src=["']([^"']+)["']""", page.body)
        if m:
            image = m.group(1)
    if image.startswith('/'):
        # Uploaded Media assets are relative (/media/…); OG scrapers require
        # absolute URLs for og:image, so prefix the canonical site base.
        from core.utils.site import site_base_url

        image = site_base_url().rstrip('/') + image
    author = (meta.get('author') or '').strip()
    if not author and getattr(page, 'author', None):
        author = (page.author.get_full_name() or page.author.get_username() or '').strip()
    # E-E-A-T + provenance for the Article JSON-LD. Authored via page.metadata
    # today (author_same_as / citations lists); the journal editor surfaces
    # these as fields in a follow-on. Lists degrade to [] when unset.
    author_same_as = _str_list(meta.get('author_same_as') or meta.get('author_links'))
    citations = _str_list(meta.get('citations') or meta.get('sources'))
    # Accurate wordCount from the FULL body (the template truncates the body it
    # passes to the JSON-LD tag, which would otherwise undercount long posts).
    word_count = len(re.sub(r'<[^>]+>', ' ', page.body or '').split())
    return {
        'id': str(page.id),
        'slug': page.slug,
        'title': page.title,
        # Visible publish date + honest reading time — e.g. "July 3, 2026 · 4 min
        # read". (The old format was "%B · %-d min read", which rendered the DAY
        # OF MONTH as a fake reading time and showed no actual date.)
        'date_label': (
            f'{pub.strftime("%B %-d, %Y")} · {_read_minutes(page.body)} min read' if pub else ''
        ),
        'excerpt': page.excerpt or '',
        'body': page.body or '',
        'published_at': pub,
        'updated_at': page.updated_at,
        'image': image,
        'author': author or 'dot books staff',
        'author_same_as': author_same_as,
        'citations': citations,
        'word_count': word_count,
        'is_html': True,
    }


def list_journal_entries(*, limit: int = 50) -> list[dict]:
    """Published CMS pages tagged with metadata.category == 'journal'."""
    from plugins.installed.cms.models import Page

    qs = (
        Page.objects.filter(state='published', metadata__category='journal')
        .exclude(publish_at__gt=timezone.now())
        .order_by('-publish_at', '-created_at')[:limit]
    )
    return [_journal_dict(p) for p in qs]


def get_journal_page(slug: str):
    """The underlying published journal ``Page`` instance (not the dict).

    The storefront journal view renders from the ``_journal_dict`` for
    display, but the SEO engine (`resolve_meta`) needs the real model
    instance as ``seo_object`` so it can load the per-page ``SeoMeta``
    override row (title/description/canonical/robots/OG) and the visual
    schema blocks (FAQ/HowTo/Event). Returns ``None`` for the seeded
    fallback entries that have no backing Page.
    """
    from plugins.installed.cms.models import Page

    return (
        Page.objects.filter(slug=slug, state='published', metadata__category='journal')
        .exclude(publish_at__gt=timezone.now())
        .first()
    )


def get_journal_entry(slug: str) -> dict | None:
    """Single published journal entry by slug, or None."""
    page = get_journal_page(slug)
    return _journal_dict(page) if page else None


def render_block(key: str) -> dict | None:
    from plugins.installed.cms.models import Block

    b = Block.objects.filter(key=key, is_active=True).first()
    if b is None:
        return None
    return {
        'key': b.key,
        'kind': b.kind,
        'label': b.label,
        'body': b.body,
        'image_url': b.image_url,
        'cta_label': b.cta_label,
        'cta_url': b.cta_url,
        'metadata': b.metadata,
    }


def get_menu(key: str) -> dict | None:
    from plugins.installed.cms.models import Menu

    m = Menu.objects.filter(key=key, is_active=True).first()
    if m is None:
        return None
    items = []
    for it in m.items.filter(parent__isnull=True).order_by('order'):
        items.append(
            {
                'label': it.label,
                'url': it.url,
                'kind': it.kind,
                'target': it.target,
                'icon': it.icon,
                'children': [
                    {
                        'label': c.label,
                        'url': c.url,
                        'kind': c.kind,
                        'target': c.target,
                        'icon': c.icon,
                    }
                    for c in it.children.all().order_by('order')
                ],
            }
        )
    return {'key': m.key, 'label': m.label, 'items': items}


def submit_form(*, form, payload: dict, request=None):
    """Persist a FormSubmission, fire `cms.form_submitted` hook."""
    from core.hooks import MorpheusEvents, hook_registry
    from plugins.installed.cms.models import FormSubmission

    ip = request.META.get('REMOTE_ADDR', '') if request else ''
    ua = request.META.get('HTTP_USER_AGENT', '') if request else ''
    submission = FormSubmission.objects.create(
        form=form,
        payload={k: str(v)[:2000] for k, v in (payload or {}).items()},
        submitter_email=(payload or {}).get('email', '')[:254],
        submitter_ip_hash=hashlib.sha256(ip.encode('utf-8')).hexdigest()[:32] if ip else '',
        user_agent=ua[:300],
    )
    try:
        hook_registry.fire(MorpheusEvents.CMS_FORM_SUBMITTED, form=form, submission=submission)
    except Exception as e:  # noqa: BLE001
        logger.warning('cms: hook fire failed: %s', e)
    return submission
