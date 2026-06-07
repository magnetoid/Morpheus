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
    author = (meta.get('author') or '').strip()
    if not author and getattr(page, 'author', None):
        author = (page.author.get_full_name() or page.author.get_username() or '').strip()
    return {
        'id': str(page.id),
        'slug': page.slug,
        'title': page.title,
        'date_label': pub.strftime('%B · %-d min read') if pub else '',
        'excerpt': page.excerpt or '',
        'body': page.body or '',
        'published_at': pub,
        'updated_at': page.updated_at,
        'image': image,
        'author': author or 'dot books staff',
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


def get_journal_entry(slug: str) -> dict | None:
    """Single published journal entry by slug, or None."""
    from plugins.installed.cms.models import Page

    page = (
        Page.objects.filter(slug=slug, state='published', metadata__category='journal')
        .exclude(publish_at__gt=timezone.now())
        .first()
    )
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
