"""Browse CJ's catalogue and bring a product into the store.

* ``search`` — ``GET /product/listV2`` (``keyWord``, ``page``, ``size``; the
  products sit in ``data.content[].productList[]``; 50 API points a call);
* ``product_spec`` — ``GET /product/query?pid=`` → the shared importer's
  :class:`~plugins.dropshipping.importer.SupplierProduct` (variants with ``vid``,
  ``variantSku``, ``variantNameEn``/``variantKey``, ``variantSellPrice`` in USD);
* ``freight_options`` — ``POST /logistic/freightCalculate``;
* ``import_cj_product`` — import through the shared importer, then link every
  variant (``CJLink``) and subscribe the product to CJ's stock/price webhooks.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation

from plugins.dropshipping.importer import store_currency
from plugins.installed.cjdropshipping.services.client import CJError, config, request

logger = logging.getLogger('morpheus.cjdropshipping')

_NUMBER = re.compile(r'\d+(?:\.\d+)?')


def _price(value) -> Decimal:
    """A CJ price — a number, a numeric string, or a range like "8.13-8.62" (low end)."""
    match = _NUMBER.search(str(value if value is not None else ''))
    try:
        return Decimal(match.group(0)) if match else Decimal('0')
    except InvalidOperation:
        return Decimal('0')


def _images(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, str) and value:
        return [part.strip() for part in value.split(',') if part.strip()]
    return []


def search(keyword: str, *, page: int = 1, size: int = 20) -> dict:
    data = (
        request(
            'GET',
            '/product/listV2',
            params={'keyWord': keyword, 'page': max(1, page), 'size': max(1, min(size, 100))},
        )
        or {}
    )
    items = []
    for block in data.get('content') or []:
        for product in block.get('productList') or []:
            items.append(
                {
                    'pid': str(product.get('id') or ''),
                    'name': product.get('nameEn') or '',
                    'sku': product.get('sku') or '',
                    'image': product.get('bigImage') or '',
                    'price': _price(product.get('sellPrice')),
                    'inventory': product.get('warehouseInventoryNum'),
                    'supplier': product.get('supplierName') or '',
                }
            )
    return {
        'items': [i for i in items if i['pid']],
        'total': data.get('totalRecords') or len(items),
    }


def _rate() -> Decimal:
    try:
        rate = Decimal(str(config().get('usd_to_store_rate') or 1))
    except InvalidOperation:
        rate = Decimal('1')
    return rate if rate > 0 else Decimal('1')


def product_spec(pid: str):
    from plugins.dropshipping.importer import SupplierProduct, SupplierVariant  # noqa: PLC0415

    data = request('GET', '/product/query', params={'pid': pid}) or {}
    if not data:
        raise CJError(f'CJ has no product {pid}.')
    rate = _rate()
    base_cost = _price(data.get('sellPrice'))
    variants = []
    for v in data.get('variants') or []:
        vid = str(v.get('vid') or '')
        if not vid:
            continue
        cost = _price(v.get('variantSellPrice')) or base_cost
        variants.append(
            SupplierVariant(
                supplier_variant_id=vid,
                name=v.get('variantNameEn') or v.get('variantKey') or v.get('variantSku') or vid,
                sku=v.get('variantSku') or vid,
                cost=(cost * rate).quantize(Decimal('0.01')),
                image_url=v.get('variantImage') or '',
            )
        )
    images = _images(data.get('productImageSet')) or _images(data.get('bigImage'))
    return SupplierProduct(
        supplier='CJ',
        supplier_product_id=str(data.get('pid') or pid),
        title=data.get('productNameEn') or data.get('productSku') or pid,
        description_html=data.get('description') or '',
        image_urls=images + [v.image_url for v in variants if v.image_url],
        variants=variants,
        source_url=f'https://cjdropshipping.com/product/-p-{pid}.html',
    )


def ship_from() -> str:
    return (str(config().get('ship_from_country') or 'CN').strip() or 'CN').upper()[:2]


def freight_options(lines: list[dict], country_code: str, zip_code: str = '') -> list[dict]:
    """Shipping methods CJ offers for ``lines`` (``[{vid, quantity}]``) to a country, cheapest first."""
    data = (
        request(
            'POST',
            '/logistic/freightCalculate',
            json={
                'startCountryCode': ship_from(),
                'endCountryCode': country_code.upper(),
                'zip': zip_code,
                'products': [
                    {'quantity': int(line['quantity']), 'vid': line['vid']} for line in lines
                ],
            },
        )
        or []
    )
    options = [
        {
            'name': o.get('logisticName') or '',
            'price': _price(o.get('totalPostageFee') or o.get('logisticPrice')),
            'days': o.get('logisticAging') or '',
        }
        for o in data
        if o.get('logisticName')
    ]
    return sorted(options, key=lambda o: o['price'])


def import_cj_product(pid: str):
    """Import CJ product ``pid`` as a draft; returns the shared ImportResult."""
    from plugins.dropshipping.importer import import_product  # noqa: PLC0415
    from plugins.installed.cjdropshipping.models import CJLink  # noqa: PLC0415

    spec = product_spec(pid)
    cfg = config()
    try:
        markup = Decimal(str(cfg.get('price_markup') or '2'))
    except InvalidOperation:
        markup = Decimal('2')
    result = import_product(
        spec,
        markup=markup if markup > 0 else Decimal('2'),
        currency=store_currency(),
        charm=bool(cfg.get('charm_pricing', True)),
    )
    by_vid = {v.supplier_variant_id: v for v in spec.variants}
    for vid, variant in result.variants.items():
        source = by_vid[vid]
        CJLink.objects.update_or_create(
            product=result.product,
            variant=variant,
            defaults={
                'cj_product_id': spec.supplier_product_id,
                'cj_variant_id': vid,
                'cj_sku': source.sku[:100],
                'cost': source.cost,
            },
        )
    try:  # stock and price changes arrive by webhook only for subscribed products
        request(
            'POST', '/webhook/product/subscribe', json={'productIds': [spec.supplier_product_id]}
        )
    except CJError as e:
        logger.info('cjdropshipping: subscribe %s skipped: %s', spec.supplier_product_id, e.message)
    return result
