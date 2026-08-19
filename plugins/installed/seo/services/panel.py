"""The per-entity SEO panel — one editor for every kind of page.

Products, categories, collections, CMS pages and journal posts all get the
*same* editor, backed by the same `SeoMeta` row. Before v0.47 a product had
thirteen native columns edited through a bespoke block in the product form
while everything else used this panel, so the two disagreed about what SEO even
consisted of — and `SeoMeta` silently outranked the product form's own fields,
which meant a merchant could type a meta title into the product page and watch
the storefront ignore it.

`panel_context` reads the current values; `save_object_seo` writes them back
from the panel's `seo_*` POST fields. Two rules run through both:

* **Read-through.** When an entity has no `SeoMeta` row yet, the panel seeds
  itself from the host model's own SEO columns, so a merchant sees the values
  they typed before the move and the first save migrates them.
* **Presence, not absence.** `save_object_seo` does nothing unless the panel
  was actually in the submitted form. Without that, a POST from a form that
  never rendered the card writes blanks over the row — silently wiping the SEO
  and flipping a noindex page back into the index.
"""

from __future__ import annotations

# ruff: noqa: PLC0415, S110 — inline imports keep the optional seo/metafields
# plugins soft so a disabled plugin can't break a dashboard form; the broad
# try/except/pass guards make every read/write fail-soft on a disabled plugin.

_TWITTER_CARDS = {'summary', 'summary_large_image'}

# The panel's fields, and the host-model column each one falls back to while the
# native columns are still being read (they are removed in a later release).
# Ordering is the panel's own; `title` first is load-bearing for the presence
# marker below.
_NATIVE_FALLBACKS = {
    'title': 'meta_title',
    'description': 'meta_description',
    'canonical_url': 'canonical_url',
    'og_title': 'og_title',
    'og_description': 'og_description',
    'twitter_title': 'twitter_title',
    'twitter_description': 'twitter_description',
    'twitter_card': 'twitter_card',
    'focus_keyword': 'focus_keyword',
}

_MAX_LENGTHS = {
    'title': 200,
    'description': 320,
    'canonical_url': 600,
    'og_title': 200,
    'og_description': 320,
    'og_image': 600,
    'twitter_title': 200,
    'twitter_description': 320,
    'focus_keyword': 120,
    'ai_answer': 600,
}


def _clamp_twitter(value: str) -> str:
    v = (value or '').strip()
    return v if v in _TWITTER_CARDS else 'summary_large_image'


def _robots_from_post(post) -> str:
    """The panel's noindex/nofollow checkboxes → a valid robots string."""
    return '{}, {}'.format(
        'noindex' if post.get('seo_noindex') else 'index',
        'nofollow' if post.get('seo_nofollow') else 'follow',
    )


def _robots_extra_from_post(post) -> dict:
    """Advanced directives. Only non-default values are stored, so an untouched
    panel leaves the field empty rather than freezing today's defaults into
    every row."""
    extra: dict = {}
    preview = (post.get('seo_max_image_preview') or '').strip().lower()
    if preview in {'none', 'standard'}:
        extra['max_image_preview'] = preview
    try:
        snippet = int(post.get('seo_max_snippet') or -1)
    except (TypeError, ValueError):
        snippet = -1
    if snippet != -1:
        extra['max_snippet'] = snippet
    if post.get('seo_nosnippet'):
        extra['nosnippet'] = True
    if post.get('seo_noimageindex'):
        extra['noimageindex'] = True
    return extra


def _sitemap_choice(value) -> str:
    """The stored tri-state as a form value. NULL means "platform default"."""
    if value is None:
        return ''
    return 'yes' if value else 'no'


def _sitemap_from_post(post):
    choice = (post.get('seo_sitemap_include') or '').strip().lower()
    if choice == 'yes':
        return True
    if choice == 'no':
        return False
    return None


def _native(obj, field: str) -> str:
    if obj is None or not field:
        return ''
    value = getattr(obj, field, '')
    if not value:
        # An EMPTY FileField is falsy but not None, and reading `.url` on one
        # raises ValueError rather than returning ''. Almost no product has an
        # og_image, so touching it unguarded took down the whole panel — and the
        # card collector swallows exceptions, so the SEO editor simply did not
        # appear, with a 200 and nothing in the page to say why.
        return ''
    # og_image / twitter_image are ImageFields on Product; the panel stores URLs.
    try:
        url = getattr(value, 'url', None)
    except Exception:  # noqa: BLE001 — a file row pointing at missing storage
        return ''
    return str(url) if url else str(value)


_BLANK_VALUES = {
    'title': '',
    'description': '',
    'canonical_url': '',
    'robots': 'index, follow',
    'og_title': '',
    'og_description': '',
    'og_image': '',
    'twitter_card': 'summary_large_image',
    'twitter_title': '',
    'twitter_description': '',
    'focus_keyword': '',
    # '' = follow the platform default, 'yes' = always list, 'no' = never list.
    'sitemap_include': '',
}


def _stored_values(obj) -> tuple[dict, str, dict, dict]:
    """`(values, ai_answer, robots_extra, provenance)` for a saved object.

    Priority per field: the `SeoMeta` row → the host model's native column →
    blank. The read-through is what makes the move to a single owner invisible
    to the merchant: a product carrying a meta title typed before v0.47 shows
    it here instead of an empty box they would have to retype.
    """
    vals = dict(_BLANK_VALUES)
    robots_extra: dict = {}
    provenance: dict = {}
    autofilled = False
    try:
        from plugins.installed.seo.models import SeoMeta

        sm = SeoMeta.for_obj(obj)
        if sm:
            for f, default in list(vals.items()):
                vals[f] = getattr(sm, f, default) or default
            # The focus keyword used to share the legacy `keywords` column.
            vals['focus_keyword'] = sm.focus_keyword or sm.keywords or ''
            robots_extra = sm.robots_extra or {}
            provenance = sm.provenance or {}
            autofilled = bool(sm.auto_filled)
            vals['sitemap_include'] = _sitemap_choice(sm.sitemap_include)
    except Exception:  # noqa: BLE001 — seo plugin optional
        pass

    for field, native_field in _NATIVE_FALLBACKS.items():
        native = _native(obj, native_field)
        if not native:
            continue
        # An autofilled value is the platform's guess (the product's own name);
        # a native column holds what the merchant typed into the old product
        # form. Show them theirs — the same precedence the storefront applies.
        if not vals.get(field) or autofilled:
            vals[field] = native
            provenance.setdefault(field, 'native')
    if not vals['og_image']:
        vals['og_image'] = _native(obj, 'og_image')
    if vals['robots'] == 'index, follow' and (
        getattr(obj, 'noindex', False) or getattr(obj, 'nofollow', False)
    ):
        vals['robots'] = '{}, {}'.format(
            'noindex' if getattr(obj, 'noindex', False) else 'index',
            'nofollow' if getattr(obj, 'nofollow', False) else 'follow',
        )
    try:
        from plugins.installed.seo.services._helpers import ai_answer_for

        ai_answer = ai_answer_for(obj)
    except Exception:  # noqa: BLE001
        ai_answer = ''
    return vals, ai_answer, robots_extra, provenance


def panel_context(obj, request=None) -> dict:
    """Panel context for ``obj`` — stored values, or the POSTed ones on a
    validation re-render so a merchant never loses SEO edits to an unrelated
    failure (a slug clash, say)."""
    if obj is not None and getattr(obj, 'pk', None):
        vals, ai_answer, robots_extra, provenance = _stored_values(obj)
    else:
        vals, ai_answer, robots_extra, provenance = dict(_BLANK_VALUES), '', {}, {}

    # POST override (error re-render): the panel posts seo_title, so its
    # presence signals the panel was submitted.
    card_open = False
    if request is not None and getattr(request, 'method', '') == 'POST':
        p = request.POST
        if 'seo_title' in p:
            # They were working in this card when the save failed — re-render it
            # open, or their edits sit behind a collapsed summary they have to
            # find again.
            card_open = True
            vals['title'] = p.get('seo_title', '')
            vals['description'] = p.get('seo_description', '')
            vals['canonical_url'] = p.get('seo_canonical', '')
            vals['og_title'] = p.get('seo_og_title', '')
            vals['og_description'] = p.get('seo_og_description', '')
            vals['og_image'] = p.get('seo_og_image', '')
            vals['twitter_card'] = _clamp_twitter(p.get('seo_twitter_card', ''))
            vals['twitter_title'] = p.get('seo_twitter_title', '')
            vals['twitter_description'] = p.get('seo_twitter_description', '')
            vals['focus_keyword'] = p.get('seo_focus_keyword', '')
            vals['sitemap_include'] = p.get('seo_sitemap_include', '')
            vals['robots'] = _robots_from_post(p)
            robots_extra = _robots_extra_from_post(p)
            ai_answer = p.get('seo_ai_answer', '')

    title_max, desc_max = 60, 155
    brand, host = '', ''
    try:
        from plugins.installed.seo.services._helpers import _site_base_url, site_settings
        from plugins.installed.seo.services.meta import brand_name

        s = site_settings()
        title_max = int(getattr(s, 'title_max_length', 60) or 60)
        desc_max = int(getattr(s, 'description_max_length', 155) or 155)
        brand = brand_name() or ''
        host = (_site_base_url() or '').replace('https://', '').replace('http://', '').rstrip('/')
    except Exception:  # noqa: BLE001
        pass

    robots = vals['robots'] or 'index, follow'
    return {
        'seo': vals,
        'seo_ai_answer': ai_answer,
        'seo_robots_extra': robots_extra,
        'seo_provenance': provenance,
        'seo_noindex': 'noindex' in robots,
        'seo_nofollow': 'nofollow' in robots,
        'seo_title_max': title_max,
        'seo_desc_max': desc_max,
        'seo_brand': brand,
        'seo_host': host,
        'seo_object_path': _object_path(obj),
        'seo_schema_editor_url': _schema_editor_url(obj),
        'seo_card_open': card_open,
        'seo_twitter_choices': [
            ('summary_large_image', 'Summary (large image)'),
            ('summary', 'Summary'),
        ],
        'seo_sitemap_choices': [
            ('', 'Default for this page type'),
            ('yes', 'Always list it'),
            ('no', 'Keep it out'),
        ],
        'seo_image_preview_choices': [
            ('large', 'Large (recommended)'),
            ('standard', 'Standard'),
            ('none', 'No image'),
        ],
    }


def _schema_editor_url(obj) -> str:
    """The visual structured-data editor for this object.

    It travels with the panel rather than being linked from each shell's
    template: a `/dashboard/seo/…` URL written into the product and page forms
    is a hardcoded link to an optional app, and it 404s the moment seo is
    disabled instead of disappearing.
    """
    if obj is None or not getattr(obj, 'pk', None):
        return ''
    try:
        meta = obj._meta
        return f'/dashboard/seo/schema/{meta.app_label}/{meta.model_name}/{obj.pk}/'
    except Exception:  # noqa: BLE001
        return ''


def _object_path(obj) -> str:
    try:
        from plugins.installed.seo.services.slug_history import public_path_for

        return public_path_for(obj)
    except Exception:  # noqa: BLE001
        return ''


def save_object_seo(obj, post) -> None:
    """Upsert ``obj``'s SeoMeta override from the panel's ``seo_*`` POST fields.

    Fail-soft, and deliberately conservative about *when* it writes: only when
    the panel was rendered in the submitted form, and only when there is
    something to store or a row already exists (no empty clutter).
    """
    if obj is None or not getattr(obj, 'pk', None):
        return
    # The panel always posts ``seo_title`` when it's rendered; its absence means
    # the panel wasn't in the submitted form (e.g. the seo plugin is toggled off
    # but still importable). Never touch the SeoMeta row in that case — writing
    # blanks would silently wipe a page's SEO and flip a noindex page back to
    # indexable.
    if 'seo_title' not in post:
        return
    robots = _robots_from_post(post)

    def field(name: str, key: str) -> str:
        return (post.get(key) or '').strip()[: _MAX_LENGTHS.get(name, 320)]

    fields = {
        'title': field('title', 'seo_title'),
        'description': field('description', 'seo_description'),
        'canonical_url': field('canonical_url', 'seo_canonical'),
        'og_title': field('og_title', 'seo_og_title'),
        'og_description': field('og_description', 'seo_og_description'),
        'og_image': field('og_image', 'seo_og_image'),
        'twitter_card': _clamp_twitter(post.get('seo_twitter_card', '')),
        'twitter_title': field('twitter_title', 'seo_twitter_title'),
        'twitter_description': field('twitter_description', 'seo_twitter_description'),
        'focus_keyword': field('focus_keyword', 'seo_focus_keyword'),
        'ai_answer': field('ai_answer', 'seo_ai_answer'),
        'robots': robots,
        'robots_extra': _robots_extra_from_post(post),
        'sitemap_include': _sitemap_from_post(post),
        'auto_filled': False,
    }
    _text_fields = (
        'title',
        'description',
        'canonical_url',
        'og_title',
        'og_description',
        'og_image',
        'twitter_title',
        'twitter_description',
        'focus_keyword',
        'ai_answer',
    )
    try:
        from django.contrib.contenttypes.models import ContentType

        from plugins.installed.seo.models import SeoMeta

        ct = ContentType.objects.get_for_model(type(obj))
        qs = SeoMeta.objects.filter(content_type=ct, object_id=str(obj.pk))
        text_set = any(fields[k] for k in _text_fields)
        if not (
            text_set
            or robots != 'index, follow'
            or fields['robots_extra']
            or fields['sitemap_include'] is not None
            or qs.exists()
        ):
            return
        # Whatever the merchant just typed is theirs — record that, so a later
        # bulk template or AI pass can leave hand-written values alone.
        fields['provenance'] = {k: 'merchant' for k in _text_fields if fields[k]}
        SeoMeta.objects.update_or_create(content_type=ct, object_id=str(obj.pk), defaults=fields)
    except Exception:  # noqa: BLE001 — seo plugin optional
        pass
    _purge_object_url(obj)


def _purge_object_url(obj) -> None:
    """A meta change rewrites cached HTML without touching the product row, so
    the usual product/category purge never fires for it."""
    try:
        from morpheus.core import MorpheusEvents, hook_registry
        from plugins.installed.seo.services.slug_history import public_path_for

        path = public_path_for(obj)
        if path:
            hook_registry.fire(MorpheusEvents.EDGE_PURGE_URLS, urls=[path], reason='seo.meta')
    except Exception:  # noqa: BLE001 — a CDN must never fail a merchant's save
        pass
