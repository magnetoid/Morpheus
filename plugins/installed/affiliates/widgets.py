"""Embeddable shop widgets — the PUBLIC, cross-origin product surface.

This module is the single source of truth for what an embeddable
``AffiliateWidget`` exposes to the outside world. Three public endpoints
consume it (iframe HTML, JSON API, JS snippet); all of them go through
``serialize_widget`` / ``serialize_product`` so the no-PII boundary lives in
exactly one place.

SECURITY CONTRACT (read before touching ``serialize_product``):
  * Output is PUBLIC and cross-origin. It must contain ONLY data already
    visible on the public storefront PDP: name, slug, price, image, sale flag.
  * NEVER add customer / order / cost / inventory / vendor-internal fields.
  * Every product link routes through the affiliate's ``/r/<code>?next=<pdp>``
    redirect so a click attributes via the existing ``record_click`` path.
  * Only ``status='active'`` products are ever returned.
"""

# ruff: noqa: PLC0415  — inline imports match the plugin's house style and
# keep optional cross-plugin imports (catalog) lazy / load-order-safe.
from __future__ import annotations

from urllib.parse import quote


def _safe_href(url: str) -> str:
    """Defense-in-depth at the single public-boundary point: only a root-relative
    path (one leading slash, NOT protocol-relative ``//``) or an http(s) URL may
    cross into a widget card's ``href``/``src``. Blocks ``javascript:`` / ``data:``
    schemes (HTML auto-escaping does NOT neutralise these in an attribute) and
    ``//host`` redirects. The URLs we build are already safe; this guarantees it
    for every consumer — iframe template, JSON, JS snippet — from one place."""
    if not url:
        return ''
    if url.lower().startswith(('https://', 'http://')):
        return url
    if url.startswith('/') and not url.startswith('//'):
        return url
    return ''


def _active_products_qs():
    from plugins.installed.catalog.models import Product

    return Product.objects.filter(status='active')


def resolve_products(widget) -> list:
    """The ordered list of public Products this widget renders.

    Bounded by ``widget.effective_limit`` (hard cap 24). Sources:
      * ``featured``  — active + is_featured, newest first.
      * ``category``  — active products in ``category_slug`` (primary OR
        additional category), newest first.
      * ``products``  — the explicit ``product_ids``, original order preserved,
        filtered to active.
    """
    from django.db.models import Q

    limit = widget.effective_limit
    qs = _active_products_qs().select_related('category').prefetch_related('images')

    if widget.source == 'products':
        ids = [str(p) for p in (widget.product_ids or [])][:limit]
        if not ids:
            return []
        found = {str(p.id): p for p in qs.filter(id__in=ids)}
        # Preserve the operator's chosen order; drop ids that no longer
        # resolve to an active product.
        return [found[i] for i in ids if i in found]

    if widget.source == 'category':
        slug = (widget.category_slug or '').strip()
        if not slug:
            return []
        qs = qs.filter(Q(category__slug=slug) | Q(additional_categories__slug=slug)).distinct()
        return list(qs.order_by('-created_at')[:limit])

    # Default: featured.
    return list(qs.filter(is_featured=True).order_by('-created_at')[:limit])


def widget_ref_code(widget) -> str:
    """The affiliate ref code every product link in this widget uses.

    Prefers the widget's pinned ``link``; falls back to the affiliate's
    oldest active link. Returns '' when the affiliate has no usable link —
    callers then link straight to the PDP (no attribution, but no breakage).
    """
    link = widget.link if (widget.link_id and widget.link and widget.link.is_active) else None
    if link is None:
        from plugins.installed.affiliates.models import AffiliateLink

        link = (
            AffiliateLink.objects.filter(affiliate_id=widget.affiliate_id, is_active=True)
            .order_by('created_at')
            .first()
        )
    return link.code if link else ''


def product_pdp_path(product) -> str:
    """Internal storefront PDP path for a product (no host)."""
    from django.urls import reverse

    try:
        return reverse('storefront:product_detail', args=[product.slug])
    except Exception:  # noqa: BLE001 — storefront may route differently; degrade gracefully
        return f'/products/{product.slug}/'


def product_click_url(product, ref_code: str, *, base: str = '') -> str:
    """Absolute (or root-relative) click URL for a product card.

    With a ref code: ``<base>/r/<code>?next=<pdp>`` — routes the click through
    the existing affiliate redirect so ``record_click`` fires and the
    ``morph_aff`` cookie is set before the visitor lands on the PDP.
    Without one: the bare PDP (still works, just unattributed).
    """
    pdp = product_pdp_path(product)
    base = (base or '').rstrip('/')
    if not ref_code:
        return f'{base}{pdp}' if base else pdp
    return f'{base}/r/{ref_code}?next={quote(pdp, safe="")}'


def _image_url(product) -> str:
    """Public cover image URL (prefers the WebP variant). '' when none."""
    img = product.primary_image
    if not img:
        return ''
    try:
        if getattr(img, 'webp_image', None):
            return img.webp_image.url
        if getattr(img, 'image', None):
            return img.image.url
    except Exception:  # noqa: BLE001 — storage may be unconfigured in tests
        return ''
    return ''


def _fmt_money(value) -> str:
    """Display string for a Money value via the canonical storefront filter
    (locale-aware). Falls back to ``str(value)`` if anything goes wrong."""
    if value is None:
        return ''
    try:
        from core.templatetags.morph import money_filter

        return money_filter(value)
    except Exception:  # noqa: BLE001
        return str(value)


def _price_str(product) -> str:
    """Display price as a plain string (e.g. '$19.99')."""
    return _fmt_money(product.display_price)


def serialize_product(product, ref_code: str, *, base: str = '') -> dict:
    """PUBLIC, cross-origin-safe product dict. See module security contract.

    Whitelist — these fields and ONLY these fields cross the boundary:
      name, slug, price, on_sale, compare_at_price, image, url.
    """
    on_sale = bool(getattr(product, 'is_on_sale', False))
    compare = _fmt_money(product.compare_at_price) if (on_sale and product.compare_at_price) else ''
    return {
        'name': product.name,
        'slug': product.slug,
        'price': _price_str(product),
        'compare_at_price': compare,
        'on_sale': on_sale,
        'image': _safe_href(_image_url(product)),
        'url': _safe_href(product_click_url(product, ref_code, base=base)),
    }


def serialize_widget(widget, *, base: str = '') -> dict:
    """Full public payload for the JSON endpoint + JS snippet.

    No affiliate identity beyond the opaque ref code is exposed — not the
    handle, not the user, not earnings.
    """
    ref = widget_ref_code(widget)
    products = resolve_products(widget)
    return {
        'title': widget.title or '',
        'theme': widget.theme,
        'layout': widget.layout,
        'products': [serialize_product(p, ref, base=base) for p in products],
    }
