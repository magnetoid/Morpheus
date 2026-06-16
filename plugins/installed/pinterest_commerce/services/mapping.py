"""Resolve one Product into Pinterest catalog feed attributes.

Pinterest Catalog ingests the standard RSS g: feed (availability `in stock`/`out of
stock`, condition `new`, price `9.00 USD`, item_group_id for variants). Reuses
identifiers/book_attrs + per-product `pinterest.*` overrides. Returns None when
excluded / missing image+price.
"""

from __future__ import annotations

import contextlib
import logging

from django.utils.html import strip_tags

logger = logging.getLogger('morpheus.pinterest_commerce')

_GTIN_CODES = ('isbn', 'gtin13', 'gtin12', 'gtin14')
_NS = 'pinterest'
_CUSTOM_LABELS = tuple(f'custom_label_{i}' for i in range(5))


def _abs(url: str) -> str:
    from core.utils.site import site_base_url  # noqa: PLC0415

    if not url:
        return ''
    if url.startswith(('http://', 'https://')):
        return url
    return site_base_url().rstrip('/') + '/' + url.lstrip('/')


def _overrides(product) -> dict:
    try:
        from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

        raw = Metafield.objects.for_obj(product, ns=_NS) or {}
    except Exception:  # noqa: BLE001
        return {}
    return {k.split('.', 1)[-1]: v for k, v in raw.items()}


def _identifiers(product) -> tuple[str, str]:
    try:
        from plugins.installed.metafields.identifiers import product_identifiers  # noqa: PLC0415

        codes = product_identifiers(product)
    except Exception:  # noqa: BLE001
        return '', ''
    by = {c.get('jsonld'): c.get('value') for c in codes if c.get('value')}
    gtin = ''
    for code in _GTIN_CODES:
        if by.get(code):
            gtin = str(by[code]).replace('-', '').strip()
            break
    return gtin, (str(by['mpn']).strip() if by.get('mpn') else '')


def _availability_for(filter_kwargs: dict, *, include_oos: bool) -> str | None:
    avail = 'in stock'
    try:
        from django.db.models import F, Sum  # noqa: PLC0415

        from plugins.installed.inventory.models import StockLevel  # noqa: PLC0415

        qty = StockLevel.objects.filter(**filter_kwargs).aggregate(
            q=Sum(F('quantity') - F('reserved_quantity'))
        )['q']
        if qty is not None and qty <= 0:
            avail = 'out of stock'
    except Exception:  # noqa: BLE001
        avail = 'in stock'
    if avail == 'out of stock' and not include_oos:
        return None
    return avail


def _money(m) -> str:
    if m is None:
        return ''
    try:
        return f'{m.amount:.2f} {m.currency}'
    except Exception:  # noqa: BLE001
        return ''


def map_product(product, settings) -> dict | None:  # noqa: PLR0912, PLR0915 — flat resolver
    over = _overrides(product)
    if str(over.get('excluded', '')).lower() in ('1', 'true', 'yes'):
        return None

    img = getattr(product, 'primary_image', None)
    image_link = ''
    if img is not None and getattr(img, 'image', None):
        with contextlib.suppress(Exception):
            image_link = _abs(img.image.url)
    if not image_link:
        return None

    on_sale = bool(getattr(product, 'is_on_sale', False))
    base_price = getattr(product, 'display_price', None) or getattr(product, 'price', None)
    if on_sale:
        price = _money(getattr(product, 'compare_at_price', None))
        sale_price = _money(base_price)
    else:
        price = _money(base_price)
        sale_price = ''
    if not price:
        return None

    availability = _availability_for(
        {'variant__product': product}, include_oos=settings.include_out_of_stock
    )
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
    if over.get('google_product_category'):
        item['google_product_category'] = over['google_product_category']
    for label in _CUSTOM_LABELS:
        if over.get(label):
            item[label] = str(over[label])[:100]
    return item


def _variant_availability(variant, *, include_oos: bool) -> str | None:
    return _availability_for({'variant': variant}, include_oos=include_oos)


def expand_variants(product, base_item: dict, settings) -> list[dict] | None:  # noqa: PLR0912
    if getattr(product, 'product_type', '') != 'variable':
        return None
    try:
        variants = list(product.variants.filter(is_active=True))
    except Exception:  # noqa: BLE001
        return None
    if len(variants) < 2:
        return None

    items: list[dict] = []
    for v in variants:
        vi = dict(base_item)
        vi['item_group_id'] = base_item['id']
        vi['id'] = (getattr(v, 'sku', '') or '').strip() or f'{base_item["id"]}-{v.pk}'

        vprice = getattr(v, 'price', None)
        vcompare = getattr(v, 'compare_at_price', None)
        if vcompare and vprice and vcompare > vprice:
            vi['price'] = _money(vcompare)
            vi['sale_price'] = _money(vprice)
        else:
            p = _money(vprice)
            if p:
                vi['price'] = p
            vi.pop('sale_price', None)
        if not vi.get('price'):
            continue

        suffix = (getattr(v, 'name', '') or getattr(v, 'size', '') or '').strip()
        if suffix and suffix.lower() not in (base_item.get('title') or '').lower():
            vi['title'] = f'{base_item["title"]} — {suffix}'[:150]

        barcode = (getattr(v, 'barcode', '') or '').replace('-', '').strip()
        if barcode:
            vi['gtin'] = barcode

        vimg = getattr(v, 'image', None)
        if vimg is not None and getattr(vimg, 'image', None):
            with contextlib.suppress(Exception):
                vi['image_link'] = _abs(vimg.image.url)

        av = _variant_availability(v, include_oos=settings.include_out_of_stock)
        if av is None:
            continue
        vi['availability'] = av
        items.append(vi)

    return items or None
