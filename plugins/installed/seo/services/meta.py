"""Meta resolution + structured-data envelopes + autofill.

``resolve_meta`` is the canonical entry point — merges per-object
``SeoMeta`` overrides with native model SEO fields and caller-supplied
fallbacks. ``autofill_meta_for`` writes sensible defaults onto a fresh
``SeoMeta`` row the first time an object gets one.
"""
from __future__ import annotations

from typing import Any

from django.conf import settings

from ._helpers import ResolvedMeta, site_settings


def resolve_meta(
    *,
    obj: Any | None = None,
    fallback_title: str = '',
    fallback_description: str = '',
    fallback_image: str = '',
    canonical_url: str = '',
    og_type: str = 'website',
) -> ResolvedMeta:
    """Merge per-object SeoMeta + native model SEO fields + fallbacks.

    Priority order (highest first):
      1. SeoMeta row (generic-FK overrides — admin can set anything)
      2. Native model SEO fields (Product.og_title, focus_keyword, …)
      3. Provided fallbacks (whatever the caller passed)
    """
    from plugins.installed.seo.models import SeoMeta

    meta = SeoMeta.for_obj(obj) if obj is not None else None

    def native(name: str, default: str = '') -> str:
        # Pull a SEO field directly off the model instance, dict-safe.
        if obj is None:
            return default
        if isinstance(obj, dict):
            return str(obj.get(name) or default)
        return str(getattr(obj, name, '') or default)

    title = (
        (meta.title if meta and meta.title else '')
        or native('meta_title')
        or fallback_title
    ).strip()
    description = (
        (meta.description if meta and meta.description else '')
        or native('meta_description')
        or fallback_description
    ).strip()
    og_image = (
        (meta.og_image if meta and meta.og_image else '')
        or fallback_image
        or (site_settings().default_og_image or '')
    ).strip()
    canonical = (
        (meta.canonical_url if meta and meta.canonical_url else '')
        or native('canonical_url')
        or canonical_url
    ).strip()

    # Robots: SeoMeta wins; else use the model's noindex/nofollow flags.
    if meta:
        robots = meta.robots
    else:
        flags = []
        flags.append('noindex' if (obj is not None and (
            obj.get('noindex') if isinstance(obj, dict) else getattr(obj, 'noindex', False)
        )) else 'index')
        flags.append('nofollow' if (obj is not None and (
            obj.get('nofollow') if isinstance(obj, dict) else getattr(obj, 'nofollow', False)
        )) else 'follow')
        robots = ', '.join(flags)

    keywords = (meta.keywords if meta and meta.keywords else '') or native('focus_keyword')
    twitter_card = (
        (meta.twitter_card if meta else '')
        or native('twitter_card')
        or 'summary_large_image'
    )
    og_title = (meta.og_title if meta and meta.og_title else '') or native('og_title')
    og_description = (
        (meta.og_description if meta and meta.og_description else '')
        or native('og_description')
    )
    type_ = (meta.og_type if meta and meta.og_type else og_type)

    structured = _structured_data_for(obj, title=title, description=description, image=og_image)
    # Merge native model structured_data (Product.structured_data) → SeoMeta (most specific wins).
    if obj is not None and not isinstance(obj, dict):
        native_sd = getattr(obj, 'structured_data', None)
        if isinstance(native_sd, dict) and native_sd:
            structured = {**structured, **native_sd}
    if meta and meta.structured_data:
        structured = {**structured, **meta.structured_data}

    return ResolvedMeta(
        title=title,
        description=description,
        og_title=og_title,
        og_description=og_description,
        og_image=og_image,
        og_type=type_,
        twitter_card=twitter_card,
        canonical_url=canonical,
        robots=robots,
        keywords=keywords,
        structured_data=structured,
    )


def _structured_data_for(obj: Any, *, title: str, description: str, image: str) -> dict:
    """Generate sensible JSON-LD for known model types. Empty dict if unknown.

    No Organization fallback here — base.html emits the canonical
    Organization graph via `{% seo_organization_jsonld %}`, so emitting
    a stripped-down second one (only `name`) would just duplicate every
    page's <head> with two `@type: Organization` scripts.
    """
    if obj is None:
        return {}
    cls_name = type(obj).__name__
    if cls_name == 'Product':
        try:
            price_amount = str(obj.price.amount) if obj.price else ''
            price_currency = str(obj.price.currency) if obj.price else 'USD'
        except Exception:  # noqa: BLE001 — degrade gracefully on price-field oddities
            price_amount = ''
            price_currency = 'USD'
        return {
            '@context': 'https://schema.org',
            '@type': 'Product',
            'name': title or getattr(obj, 'name', ''),
            'description': description or getattr(obj, 'short_description', ''),
            'image': [image] if image else [],
            'sku': getattr(obj, 'sku', ''),
            'offers': {
                '@type': 'Offer',
                'price': price_amount,
                'priceCurrency': price_currency,
                'availability': 'https://schema.org/InStock',
            },
        }
    if cls_name in ('Category', 'Collection'):
        return {
            '@context': 'https://schema.org',
            '@type': 'CollectionPage',
            'name': title or getattr(obj, 'name', ''),
            'description': description or getattr(obj, 'description', ''),
        }
    return {}


def autofill_meta_for(obj: Any) -> 'SeoMeta | None':  # noqa: F821
    """If the merchant left meta fields blank, fill them with sensible defaults
    derived from the host model. The AI plugin can override this later."""
    from django.contrib.contenttypes.models import ContentType

    from plugins.installed.seo.models import SeoMeta

    ct = ContentType.objects.get_for_model(type(obj))
    meta, _ = SeoMeta.objects.get_or_create(content_type=ct, object_id=str(obj.pk))

    if not meta.title:
        meta.title = (
            f'{getattr(obj, "name", "")} — {getattr(settings, "STORE_NAME", "Morpheus Store")}'
        ).strip(' —')
    if not meta.description:
        desc = getattr(obj, 'short_description', '') or getattr(obj, 'description', '')
        meta.description = (desc or '')[:300]
    if not meta.og_image:
        primary = getattr(obj, 'primary_image', None)
        if primary and getattr(primary, 'image', None):
            try:
                meta.og_image = primary.image.url
            except Exception:  # noqa: BLE001 — image may not have a URL on disk
                pass
    if not meta.auto_filled:
        meta.auto_filled = True
    meta.save()
    return meta
