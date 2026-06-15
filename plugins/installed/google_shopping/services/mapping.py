"""Resolve one Product into Google Merchant feed attributes.

The single source of truth for feed-field resolution: reuses the catalog's own
price/image/inventory, `metafields.identifiers` for GTIN/MPN,
`book_product.compat.book_attrs` for brand/language, and per-product overrides
in the ``google.*`` metafield namespace (which win over settings defaults).

`map_product` returns a flat ``{attr: value}`` dict, or ``None`` when the
product is excluded or missing a hard-required attribute (image or price) — a
skip, never a feed-breaking error.
"""

from __future__ import annotations

import logging

from django.utils.html import strip_tags

logger = logging.getLogger('morpheus.google_shopping')

# identifiers whose jsonld code is a real GTIN (in priority order).
_GTIN_CODES = ('isbn', 'gtin13', 'gtin12', 'gtin14')
_GOOGLE_NS = 'google'
_CUSTOM_LABELS = tuple(f'custom_label_{i}' for i in range(5))


def _abs(url: str) -> str:
    from core.utils.site import site_base_url  # noqa: PLC0415

    if not url:
        return ''
    if url.startswith(('http://', 'https://')):
        return url
    return site_base_url().rstrip('/') + '/' + url.lstrip('/')


def _google_overrides(product) -> dict:
    """Bare-key ``google.*`` metafield dict for per-product overrides."""
    try:
        from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

        raw = Metafield.objects.for_obj(product, ns=_GOOGLE_NS) or {}
    except Exception:  # noqa: BLE001
        return {}
    return {k.split('.', 1)[-1]: v for k, v in raw.items()}


def _identifiers(product) -> tuple[str, str]:
    """(gtin, mpn) resolved from the identifiers namespace."""
    try:
        from plugins.installed.metafields.identifiers import product_identifiers  # noqa: PLC0415

        codes = product_identifiers(product)
    except Exception:  # noqa: BLE001
        return '', ''
    gtin = mpn = ''
    by_jsonld = {c.get('jsonld'): c.get('value') for c in codes if c.get('value')}
    for code in _GTIN_CODES:
        if by_jsonld.get(code):
            gtin = str(by_jsonld[code]).replace('-', '').strip()
            break
    if by_jsonld.get('mpn'):
        mpn = str(by_jsonld['mpn']).strip()
    return gtin, mpn


def _availability(product, *, include_oos: bool) -> str | None:
    """'in_stock' / 'out_of_stock'; None means "skip this product"."""
    avail = 'in_stock'
    try:
        from django.db.models import F, Sum  # noqa: PLC0415

        from plugins.installed.inventory.models import StockLevel  # noqa: PLC0415

        qty = StockLevel.objects.filter(variant__product=product).aggregate(
            q=Sum(F('quantity') - F('reserved_quantity'))
        )['q']
        # qty is None when nothing tracks this product → treat as available.
        if qty is not None and qty <= 0:
            avail = 'out_of_stock'
    except Exception:  # noqa: BLE001 — no inventory plugin → assume available
        avail = 'in_stock'
    if avail == 'out_of_stock' and not include_oos:
        return None
    return avail


def _money(m) -> str:
    """Money → '9.00 USD' (Google's price format). '' if unusable."""
    if m is None:
        return ''
    try:
        return f'{m.amount:.2f} {m.currency}'
    except Exception:  # noqa: BLE001
        return ''


def map_product(product, settings) -> dict | None:  # noqa: PLR0912, PLR0915 — flat field resolver
    over = _google_overrides(product)
    if str(over.get('excluded', '')).lower() in ('1', 'true', 'yes'):
        return None

    img = getattr(product, 'primary_image', None)
    image_link = ''
    if img is not None and getattr(img, 'image', None):
        try:
            image_link = _abs(img.image.url)
        except Exception:  # noqa: BLE001
            image_link = ''
    if not image_link:
        return None  # Google requires image_link

    on_sale = bool(getattr(product, 'is_on_sale', False))
    base_price = getattr(product, 'display_price', None) or getattr(product, 'price', None)
    if on_sale:
        price = _money(getattr(product, 'compare_at_price', None))
        sale_price = _money(base_price)
    else:
        price = _money(base_price)
        sale_price = ''
    if not price:
        return None  # Google requires price

    availability = _availability(product, include_oos=settings.include_out_of_stock)
    if availability is None:
        return None

    book = {}
    try:
        from plugins.installed.book_product.compat import book_attrs  # noqa: PLC0415

        book = book_attrs(product) or {}
    except Exception:  # noqa: BLE001
        book = {}

    gtin, mpn = _identifiers(product)
    brand = over.get('brand') or settings.default_brand or book.get('publisher') or ''
    condition = over.get('condition') or settings.default_condition or 'new'
    gpc = over.get('google_product_category') or settings.default_google_product_category or ''

    item: dict = {
        'id': (getattr(product, 'sku', '') or str(product.pk)).strip(),
        'title': (product.name or '')[:150],
        'description': strip_tags(getattr(product, 'description', '') or '')[:5000].strip()
        or (product.name or ''),
        'link': _abs(f'/products/{product.slug}/'),
        'image_link': image_link,
        'availability': availability,
        'price': price,
        'condition': condition,
    }
    if sale_price:
        item['sale_price'] = sale_price
    if brand:
        item['brand'] = brand
    if gtin:
        item['gtin'] = gtin
    if mpn:
        item['mpn'] = mpn
    if not (gtin or mpn or brand):
        # Google requires this flag for items with no unique product identifier.
        item['identifier_exists'] = 'no'
    if gpc:
        item['google_product_category'] = gpc

    # product_type = the store's own genre/category path (helps Google + Ads
    # bidding by category). Books → first genre; else category name.
    ptype = over.get('product_type') or _store_product_type(product, book)
    if ptype:
        item['product_type'] = ptype[:750]

    if book.get('language') or settings.language:
        item['content_language'] = book.get('language') or settings.language
    if getattr(product, 'requires_shipping', True) is False:
        item['shipping_weight'] = ''  # digital — no weight

    for label in _CUSTOM_LABELS:
        if over.get(label):
            item[label] = str(over[label])[:100]

    return item


def _store_product_type(product, book) -> str:
    try:
        from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

        bp = BookProduct.objects.filter(product=product).first()
        if bp is not None:
            g = bp.genres.first()
            if g is not None:
                return f'Books > {g.name}'
    except Exception:  # noqa: BLE001, S110
        pass
    cat = getattr(product, 'category', None)
    return getattr(cat, 'name', '') or ''
