"""Push products to Google Merchant Center via the Content API for Shopping.

REST (Content API v2.1) over `requests` + an OAuth2 access token — no SDK. Maps
each eligible product (services.mapping) into a Content API product resource and
upserts them in batches. Writes a GoogleSyncLog row. Graceful no-op when the
plugin isn't connected (no OAuth) or has no merchant id.

    POST https://shoppingcontent.googleapis.com/content/v2.1/{merchantId}/products/batch
"""

from __future__ import annotations

import logging

from .google_auth import access_token, is_connected
from .mapping import map_product
from .settings import feed_settings, raw_config

logger = logging.getLogger('morpheus.google_shopping')

_BATCH_URL = 'https://shoppingcontent.googleapis.com/content/v2.1/{mid}/products/batch'
_BATCH_SIZE = 200


def _content_product(item: dict, settings) -> dict:
    """Feed-attr dict (from map_product) → Content API product resource."""
    price_amount, _, price_cur = (item.get('price') or '').partition(' ')
    res: dict = {
        'offerId': item['id'],
        'title': item['title'],
        'description': item.get('description', ''),
        'link': item['link'],
        'imageLink': item['image_link'],
        'contentLanguage': item.get('content_language') or settings.language or 'en',
        'targetCountry': settings.country or 'US',
        'channel': 'online',
        'availability': item['availability'].replace('_', ' '),
        'condition': item.get('condition', 'new'),
        'price': {'value': price_amount, 'currency': price_cur},
    }
    if item.get('sale_price'):
        sp_amount, _, sp_cur = item['sale_price'].partition(' ')
        res['salePrice'] = {'value': sp_amount, 'currency': sp_cur}
    if item.get('brand'):
        res['brand'] = item['brand']
    if item.get('gtin'):
        res['gtin'] = item['gtin']
    if item.get('mpn'):
        res['mpn'] = item['mpn']
    if item.get('identifier_exists') == 'no':
        res['identifierExists'] = False
    if item.get('google_product_category'):
        res['googleProductCategory'] = item['google_product_category']
    if item.get('product_type'):
        res['productTypes'] = [item['product_type']]
    return res


def push_products(*, dry_run: bool = False) -> dict:
    """Upsert every eligible product to Merchant Center. Returns a stats dict."""
    settings = feed_settings()
    mid = (raw_config().get('merchant_id', '') or '').strip()

    if not is_connected() or not mid:
        return {'ok': False, 'reason': 'not_connected', 'sent': 0, 'errors': []}

    from plugins.installed.catalog.models import Product  # noqa: PLC0415

    entries = []
    qs = Product.objects.filter(status='active').select_related('category')
    for product in qs.iterator():
        try:
            item = map_product(product, settings)
        except Exception:  # noqa: BLE001
            item = None
        if item is None:
            continue
        entries.append(
            {
                'batchId': len(entries) + 1,
                'merchantId': mid,
                'method': 'insert',
                'product': _content_product(item, settings),
            }
        )

    if dry_run:
        return {'ok': True, 'reason': 'dry_run', 'sent': len(entries), 'errors': []}

    sent, errors = _post_batches(mid, entries)
    _log(sent, errors)
    return {'ok': not errors, 'sent': sent, 'errors': errors}


def _post_batches(mid: str, entries: list[dict]) -> tuple[int, list[str]]:
    token = access_token()
    if not token:
        return 0, ['no_access_token']

    import requests  # noqa: PLC0415

    url = _BATCH_URL.format(mid=mid)
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    sent = 0
    errors: list[str] = []
    for i in range(0, len(entries), _BATCH_SIZE):
        chunk = entries[i : i + _BATCH_SIZE]
        try:
            resp = requests.post(url, json={'entries': chunk}, headers=headers, timeout=30)
            resp.raise_for_status()
            for r in resp.json().get('entries', []):
                if r.get('errors'):
                    errors.append(str(r['errors'])[:300])
                else:
                    sent += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f'batch {i // _BATCH_SIZE}: {e}'[:300])
            logger.warning('google_shopping: content batch failed: %s', e)
    return sent, errors


def _log(sent: int, errors: list[str]) -> None:
    try:
        from plugins.installed.google_shopping.models import GoogleSyncLog  # noqa: PLC0415

        status = (
            GoogleSyncLog.STATUS_OK
            if not errors
            else (GoogleSyncLog.STATUS_PARTIAL if sent else GoogleSyncLog.STATUS_ERROR)
        )
        GoogleSyncLog.objects.create(
            kind=GoogleSyncLog.KIND_CONTENT_API,
            status=status,
            item_count=sent,
            errors=errors[:50],
            message=f'Content API push: {sent} sent, {len(errors)} errors',
        )
    except Exception as e:  # noqa: BLE001
        logger.debug('google_shopping: content-api log failed: %s', e)
