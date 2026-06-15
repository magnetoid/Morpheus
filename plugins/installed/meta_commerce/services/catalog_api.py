"""Push products to a Meta catalog via the Graph API items_batch endpoint.

    POST /{catalog_id}/items_batch
    { item_type: PRODUCT_ITEM, requests: [{ method: UPDATE, data: {...} }] }

Maps each eligible product (services.mapping) into a Meta catalog item. Batches,
writes a MetaSyncLog row, graceful no-op when not connected.
"""

from __future__ import annotations

import json
import logging

from .graph import catalog_connected, creds, get, post
from .mapping import map_product
from .settings import meta_settings

logger = logging.getLogger('morpheus.meta_commerce')

_BATCH_SIZE = 100  # Meta caps items_batch at 100 requests per call.


def _catalog_item(item: dict) -> dict:
    """Feed-attr dict → Meta catalog item resource (snake_case fields)."""
    res = {
        'retailer_id': item['id'],
        'title': item['title'],
        'description': item.get('description', ''),
        'availability': item['availability'].replace(' ', '_'),  # in stock → in_stock
        'condition': item.get('condition', 'new'),
        'price': item['price'],  # "9.00 USD"
        'link': item['link'],
        'image_link': item['image_link'],
        'brand': item.get('brand', '') or 'Generic',
    }
    if item.get('sale_price'):
        res['sale_price'] = item['sale_price']
    if item.get('gtin'):
        res['gtin'] = item['gtin']
    if item.get('mpn'):
        res['mpn'] = item['mpn']
    if item.get('item_group_id'):
        res['item_group_id'] = item['item_group_id']
    if item.get('google_product_category'):
        res['google_product_category'] = item['google_product_category']
    if item.get('fb_product_category'):
        res['fb_product_category'] = item['fb_product_category']
    return res


def push_products(*, dry_run: bool = False) -> dict:
    settings = meta_settings()
    catalog_id = creds()['catalog_id']
    if not catalog_connected():
        return {'ok': False, 'reason': 'not_connected', 'sent': 0, 'errors': []}

    from plugins.installed.catalog.models import Product  # noqa: PLC0415
    from plugins.installed.meta_commerce.services.mapping import expand_variants  # noqa: PLC0415

    requests_list: list[dict] = []
    for product in Product.objects.filter(status='active').select_related('category').iterator():
        try:
            base = map_product(product, settings)
        except Exception:  # noqa: BLE001
            base = None
        if base is None:
            continue
        for it in expand_variants(product, base, settings) or [base]:
            requests_list.append({'method': 'UPDATE', 'data': _catalog_item(it)})

    if dry_run:
        return {'ok': True, 'reason': 'dry_run', 'sent': len(requests_list), 'errors': []}

    sent, errors = _post_batches(catalog_id, requests_list)
    _log(sent, errors)
    return {'ok': not errors, 'sent': sent, 'errors': errors}


def product_diagnostics(*, max_pages: int = 4) -> dict:
    """Catalog product review status → why items are rejected/limited.

    `GET /{catalog_id}/products?fields=review_status,errors` — summarises
    approved/pending/rejected counts + the top item-level issues. Graceful no-op
    when not connected. The Meta parallel of Google Merchant diagnostics.
    """
    catalog_id = creds()['catalog_id']
    if not catalog_connected():
        return {'ok': False, 'reason': 'not_connected'}

    counts = {'approved': 0, 'pending': 0, 'rejected': 0, 'other': 0, 'total': 0}
    issues: dict[str, dict] = {}
    after = None
    for _ in range(max_pages):
        params = {'fields': 'review_status,errors', 'limit': 200}
        if after:
            params['after'] = after
        res = get(f'{catalog_id}/products', params)
        if not res.get('ok'):
            return {'ok': False, 'reason': res.get('reason')}
        data = res['data']
        for prod in data.get('data', []):
            counts['total'] += 1
            status = (prod.get('review_status') or '').lower()
            if status in counts:
                counts[status] += 1
            else:
                counts['other'] += 1
            for err in prod.get('errors', []) or []:
                key = err.get('message') or err.get('type') or 'issue'
                row = issues.setdefault(key, {'description': key, 'count': 0})
                row['count'] += 1
        after = (data.get('paging', {}).get('cursors', {}) or {}).get('after')
        if not after:
            break

    top = sorted(issues.values(), key=lambda r: r['count'], reverse=True)[:20]
    return {'ok': True, 'counts': counts, 'issues': top}


def _post_batches(catalog_id: str, requests_list: list[dict]) -> tuple[int, list[str]]:
    sent = 0
    errors: list[str] = []
    for i in range(0, len(requests_list), _BATCH_SIZE):
        chunk = requests_list[i : i + _BATCH_SIZE]
        res = post(
            f'{catalog_id}/items_batch',
            {'item_type': 'PRODUCT_ITEM', 'requests': json.dumps(chunk)},
        )
        if res.get('ok'):
            sent += len(chunk)
        else:
            errors.append(f'batch {i // _BATCH_SIZE}: {res.get("reason")}'[:300])
    return sent, errors


def _log(sent: int, errors: list[str]) -> None:
    try:
        from plugins.installed.meta_commerce.models import MetaSyncLog  # noqa: PLC0415

        status = (
            MetaSyncLog.STATUS_OK
            if not errors
            else (MetaSyncLog.STATUS_PARTIAL if sent else MetaSyncLog.STATUS_ERROR)
        )
        MetaSyncLog.objects.create(
            kind=MetaSyncLog.KIND_CATALOG_API,
            status=status,
            item_count=sent,
            errors=errors[:50],
            message=f'Catalog API push: {sent} sent, {len(errors)} errors',
        )
    except Exception as e:  # noqa: BLE001
        logger.debug('meta_commerce: catalog log failed: %s', e)
