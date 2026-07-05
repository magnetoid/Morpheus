"""Reusable per-object SEO settings panel.

One panel, one storage. Any dashboard edit form drops in
``{% seo_meta_panel obj %}`` (see templatetags/seo.py) and calls
``save_object_seo(obj, request.POST)`` on save — so pages, blogs, journals
(and, later, products/categories) all get the *identical* SEO editor backed
by the ``SeoMeta`` generic-FK override plus the ``seo.ai_answer`` metafield,
instead of each content type hand-rolling a bespoke panel.

``panel_context`` reads the current values (SeoMeta + ai_answer + site
limits); ``save_object_seo`` upserts them from the panel's ``seo_*`` POST
fields. Both fail soft — a missing seo/metafields plugin never breaks a form.
"""

from __future__ import annotations

# ruff: noqa: PLC0415, S110 — inline imports keep the optional seo/metafields
# plugins soft so a disabled plugin can't break a dashboard form; the broad
# try/except/pass guards make every read/write fail-soft on a disabled plugin.

_TWITTER_CARDS = {'summary', 'summary_large_image'}


def _clamp_twitter(value: str) -> str:
    v = (value or '').strip()
    return v if v in _TWITTER_CARDS else 'summary_large_image'


def _robots_from_post(post) -> str:
    """The panel's noindex/nofollow checkboxes → a valid robots string."""
    return '{}, {}'.format(
        'noindex' if post.get('seo_noindex') else 'index',
        'nofollow' if post.get('seo_nofollow') else 'follow',
    )


def panel_context(obj, request=None) -> dict:
    """Current SEO-panel values for ``obj``: the SeoMeta override + the
    ``seo.ai_answer`` metafield + the site title/description length limits.

    On an error re-render the POSTed ``seo_*`` values win, so a merchant
    never loses SEO edits to a validation failure (e.g. a slug clash).
    """
    vals = {
        'title': '',
        'description': '',
        'canonical_url': '',
        'robots': 'index, follow',
        'og_title': '',
        'og_description': '',
        'og_image': '',
        'twitter_card': 'summary_large_image',
        'keywords': '',
    }
    ai_answer = ''
    has_pk = obj is not None and getattr(obj, 'pk', None)
    if has_pk:
        try:
            from plugins.installed.seo.models import SeoMeta

            sm = SeoMeta.for_obj(obj)
            if sm:
                for f, default in list(vals.items()):
                    vals[f] = getattr(sm, f, default) or default
        except Exception:  # noqa: BLE001 — seo plugin optional
            pass
        try:
            from plugins.installed.seo.services._helpers import ai_answer_for

            ai_answer = ai_answer_for(obj)
        except Exception:  # noqa: BLE001
            ai_answer = ''

    # POST override (error re-render): the panel posts seo_title, so its
    # presence signals the panel was submitted.
    if request is not None and getattr(request, 'method', '') == 'POST':
        p = request.POST
        if 'seo_title' in p:
            vals['title'] = p.get('seo_title', '')
            vals['description'] = p.get('seo_description', '')
            vals['canonical_url'] = p.get('seo_canonical', '')
            vals['og_title'] = p.get('seo_og_title', '')
            vals['og_description'] = p.get('seo_og_description', '')
            vals['og_image'] = p.get('seo_og_image', '')
            vals['twitter_card'] = _clamp_twitter(p.get('seo_twitter_card', ''))
            vals['keywords'] = p.get('seo_keywords', '')
            vals['robots'] = _robots_from_post(p)
            ai_answer = p.get('seo_ai_answer', '')

    title_max, desc_max = 60, 160
    try:
        from plugins.installed.seo.models import SiteSeoSettings

        s = SiteSeoSettings.objects.first()
        if s:
            title_max = int(getattr(s, 'title_max_length', 60) or 60)
            desc_max = int(getattr(s, 'description_max_length', 160) or 160)
    except Exception:  # noqa: BLE001
        pass

    robots = vals['robots'] or 'index, follow'
    brand, host = '', ''
    try:
        from plugins.installed.seo.services._helpers import _site_base_url
        from plugins.installed.seo.services.meta import brand_name

        brand = brand_name() or ''
        host = (_site_base_url() or '').replace('https://', '').replace('http://', '').rstrip('/')
    except Exception:  # noqa: BLE001
        pass
    return {
        'seo': vals,
        'seo_ai_answer': ai_answer,
        'seo_noindex': 'noindex' in robots,
        'seo_nofollow': 'nofollow' in robots,
        'seo_title_max': title_max,
        'seo_desc_max': desc_max,
        'seo_brand': brand,
        'seo_host': host,
        'seo_twitter_choices': [
            ('summary_large_image', 'Summary (large image)'),
            ('summary', 'Summary'),
        ],
    }


def save_object_seo(obj, post) -> None:
    """Upsert ``obj``'s SeoMeta override + ``seo.ai_answer`` metafield from
    the panel's ``seo_*`` POST fields. Combines the noindex/nofollow
    checkboxes into the ``robots`` string. Fail-soft; only writes when
    there's content or an existing row (no empty clutter)."""
    if obj is None or not getattr(obj, 'pk', None):
        return
    # The panel always posts ``seo_title`` when it's rendered; its absence means
    # the panel wasn't in the submitted form (e.g. the seo plugin is toggled off
    # but still importable). Never touch the SeoMeta row / ai_answer metafield in
    # that case — writing blanks would silently wipe a page's SEO and flip a
    # noindex page back to indexable.
    if 'seo_title' not in post:
        return
    robots = _robots_from_post(post)
    fields = {
        'title': (post.get('seo_title') or '').strip()[:200],
        'description': (post.get('seo_description') or '').strip()[:320],
        'canonical_url': (post.get('seo_canonical') or '').strip()[:600],
        'og_title': (post.get('seo_og_title') or '').strip()[:200],
        'og_description': (post.get('seo_og_description') or '').strip()[:320],
        'og_image': (post.get('seo_og_image') or '').strip()[:600],
        'twitter_card': _clamp_twitter(post.get('seo_twitter_card', '')),
        'keywords': (post.get('seo_keywords') or '').strip()[:255],
        'robots': robots,
        'auto_filled': False,
    }
    try:
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.seo.models import SeoMeta

        ct = ContentType.objects.get_for_model(type(obj))
        qs = SeoMeta.objects.filter(content_type=ct, object_id=str(obj.pk))
        # "Meaningful" = any text field set, a non-default robots, or an
        # existing row (so clearing a field persists).
        text_set = any(
            fields[k]
            for k in (
                'title',
                'description',
                'canonical_url',
                'og_title',
                'og_description',
                'og_image',
                'keywords',
            )
        )
        if text_set or robots != 'index, follow' or qs.exists():
            SeoMeta.objects.update_or_create(
                content_type=ct, object_id=str(obj.pk), defaults=fields
            )
    except Exception:  # noqa: BLE001 — seo plugin optional
        pass

    # AI answer / quotable TL;DR → seo.ai_answer metafield (what the on-page
    # answer block + Article disambiguatingDescription read).
    ai = (post.get('seo_ai_answer') or '').strip()[:600]
    try:
        from plugins.installed.metafields.models import Metafield

        if ai:
            Metafield.objects.set(
                obj, namespace='seo', key='ai_answer', value=ai, value_type='string'
            )
        else:
            Metafield.objects.delete_for(obj, namespace='seo', key='ai_answer')
    except Exception:  # noqa: BLE001 — metafields plugin optional
        pass
