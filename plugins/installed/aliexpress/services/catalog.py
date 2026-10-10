"""Browse AliExpress' dropshipping catalogue and bring a product into the store.

* ``search`` — ``aliexpress.ds.text.search`` (``keyWord``, ``local``,
  ``countryCode``, ``currency``, ``pageSize``, ``pageIndex``) → ``data.products[]``;
* ``product_spec`` — ``aliexpress.ds.product.get`` (``product_id``,
  ``ship_to_country``, ``target_currency``, ``target_language``) → the shared
  importer's spec: ``ae_item_base_info_dto.subject``/``detail``,
  ``ae_multimedia_info_dto.image_urls`` (";"-separated), and the SKU list
  ``ae_item_sku_info_dtos[]`` (``sku_id``, ``sku_attr``, ``offer_sale_price``,
  ``sku_available_stock``, ``ae_sku_property_dtos[]``);
* ``freight_options`` — ``aliexpress.ds.freight.query`` with ``queryDeliveryReq``;
  the option ``code`` is what an order names as ``logistics_service_name``.

Prices come back in the store's currency (``target_currency``) for the account
whose token is used, so the cost needs no conversion.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation

from plugins.dropshipping.importer import store_currency
from plugins.installed.aliexpress.services.client import AEError, call, config

logger = logging.getLogger('morpheus.aliexpress')

_NUMBER = re.compile(r'\d+(?:\.\d+)?')


def _price(value) -> Decimal:
    match = _NUMBER.search(str(value if value is not None else '').replace(',', ''))
    try:
        return Decimal(match.group(0)) if match else Decimal('0')
    except InvalidOperation:
        return Decimal('0')


def ship_to() -> str:
    return (str(config().get('ship_to_country') or 'US').strip() or 'US').upper()[:3]


def ae_country(code: str) -> str:
    """AliExpress calls the United Kingdom "UK"; every other ISO code passes through."""
    code = (code or '').upper()
    return 'UK' if code == 'GB' else code


def search(keyword: str, *, page: int = 1, size: int = 20) -> dict:
    payload = call(
        'aliexpress.ds.text.search',
        {
            'keyWord': keyword,
            'local': 'en_US',
            'countryCode': ae_country(ship_to()),
            'currency': store_currency(),
            'pageSize': max(1, min(size, 50)),
            'pageIndex': max(1, page),
        },
    )
    data = payload.get('data') or {}
    items = []
    for p in data.get('products') or []:
        item_id = str(p.get('itemId') or '')
        if not item_id:
            continue
        items.append(
            {
                'id': item_id,
                'name': p.get('title') or '',
                'image': p.get('itemMainPic') or '',
                'price': _price(p.get('targetSalePrice') or p.get('salePrice')),
                'currency': p.get('targetOriginalPriceCurrency')
                or p.get('salePriceCurrency')
                or '',
                'orders': p.get('orders') or '',
                'rating': p.get('evaluateRate') or '',
                'url': p.get('itemUrl') or f'https://www.aliexpress.com/item/{item_id}.html',
            }
        )
    return {'items': items, 'total': data.get('totalCount') or len(items)}


def _sku_name(sku: dict) -> str:
    parts = []
    for prop in sku.get('ae_sku_property_dtos') or []:
        value = prop.get('property_value_definition_name') or prop.get('sku_property_value') or ''
        if value:
            parts.append(str(value))
    return ' / '.join(parts) or str(sku.get('sku_attr') or sku.get('sku_id') or '')


def _sku_image(sku: dict) -> str:
    for prop in sku.get('ae_sku_property_dtos') or []:
        if prop.get('sku_image'):
            return str(prop['sku_image'])
    return ''


def product_detail(product_id: str) -> dict:
    payload = call(
        'aliexpress.ds.product.get',
        {
            'product_id': product_id,
            'ship_to_country': ae_country(ship_to()),
            'target_currency': store_currency(),
            'target_language': 'en',
        },
    )
    result = payload.get('result') or {}
    if not result or not result.get('ae_item_base_info_dto'):
        raise AEError(
            str(
                payload.get('rsp_msg')
                or f'AliExpress has no product {product_id} for this country.'
            )
        )
    return result


def product_spec(product_id: str):
    from plugins.dropshipping.importer import SupplierProduct, SupplierVariant  # noqa: PLC0415

    result = product_detail(product_id)
    base = result.get('ae_item_base_info_dto') or {}
    media = result.get('ae_multimedia_info_dto') or {}
    images = [u.strip() for u in str(media.get('image_urls') or '').split(';') if u.strip()]
    variants = []
    for sku in result.get('ae_item_sku_info_dtos') or []:
        sku_id = str(sku.get('sku_id') or '')
        if not sku_id:
            continue
        cost = _price(sku.get('offer_sale_price') or sku.get('sku_price'))
        variants.append(
            SupplierVariant(
                supplier_variant_id=sku_id,
                name=_sku_name(sku),
                sku=sku_id,
                cost=cost,
                image_url=_sku_image(sku),
                stock=_int(sku.get('sku_available_stock')),
            )
        )
    return SupplierProduct(
        supplier='AE',
        supplier_product_id=str(base.get('product_id') or product_id),
        title=base.get('subject') or product_id,
        description_html=base.get('detail') or base.get('mobile_detail') or '',
        image_urls=images + [v.image_url for v in variants if v.image_url],
        variants=variants,
        source_url=f'https://www.aliexpress.com/item/{product_id}.html',
    ), result


def _int(value) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def freight_options(product_id: str, sku_id: str, quantity: int, country_code: str) -> list[dict]:
    payload = call(
        'aliexpress.ds.freight.query',
        {
            'queryDeliveryReq': {
                'quantity': int(quantity),
                'shipToCountry': ae_country(country_code),
                'productId': str(product_id),
                'selectedSkuId': str(sku_id),
                'language': 'en_US',
                'locale': 'en_US',
                'currency': store_currency(),
            }
        },
    )
    result = payload.get('result') or {}
    options = [
        {
            'code': o.get('code') or '',
            'company': o.get('company') or '',
            'price': Decimal('0')
            if str(o.get('free_shipping')).lower() == 'true'
            else _price(o.get('shipping_fee_cent')),
            'days': f'{o.get("min_delivery_days") or "?"}–{o.get("max_delivery_days") or "?"}',
        }
        for o in result.get('delivery_options') or []
        if o.get('code')
    ]
    return sorted(options, key=lambda o: o['price'])


def import_ae_product(product_id: str):
    """Import AliExpress product ``product_id`` as a draft; returns the shared ImportResult."""
    from plugins.dropshipping.importer import import_product  # noqa: PLC0415
    from plugins.installed.aliexpress.models import AELink  # noqa: PLC0415

    spec, raw = product_spec(product_id)
    cfg = config()
    try:
        markup = Decimal(str(cfg.get('price_markup') or '2'))
    except InvalidOperation:
        markup = Decimal('2')
    currency = store_currency()
    result = import_product(
        spec,
        markup=markup if markup > 0 else Decimal('2'),
        currency=currency,
        charm=bool(cfg.get('charm_pricing', True)),
    )
    skus = {str(s.get('sku_id')): s for s in raw.get('ae_item_sku_info_dtos') or []}
    by_id = {v.supplier_variant_id: v for v in spec.variants}
    for sku_id, variant in result.variants.items():
        sku = skus.get(sku_id, {})
        AELink.objects.update_or_create(
            product=result.product,
            variant=variant,
            defaults={
                'ae_product_id': spec.supplier_product_id,
                'ae_sku_id': sku_id,
                'sku_attr': str(sku.get('sku_attr') or '') if len(skus) > 1 else '',
                'cost': by_id[sku_id].cost,
                'currency': currency,
                'stock': by_id[sku_id].stock,
            },
        )
    return result
