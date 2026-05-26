"""Bookvault API client + business-logic helpers.

Three external endpoints we talk to (host: ``*.bookvault.app``):

  * ``auth.bookvault.app/api/WooAuth?storeUrl=<url>`` (GET)
        Mints ``Token`` + ``StoreID`` + ``Authenticated`` for this
        store's URL. Run from the dashboard "Connect" button (the WP
        plugin did it on plugin-update; we expose it as an explicit
        admin action).

  * ``webhooks.bookvault.app/woocommerce/shipping`` (POST)
        Body: ``{OrderLines: [{ISBN, Quantity}], CountryCode,
        ServiceLevel, AreaCode}``. Returns
        ``{Services: [{ServID, ServName, ServDetail, DelTotal}]}`` —
        the available print-and-ship services + landed cost. Only
        13-digit SKUs (= ISBNs) participate.

  * ``webhooks.bookvault.app/woocommerce/orders/create`` (POST)
        Forwards a paid order. Returns the BV order ref (``BVRef`` in
        the WP plugin), persisted on ``BookvaultOrderLink.bv_ref``.

Every call uses a 60-second timeout + JSON content type, mirroring the
WP plugin's ``bvlt_get_shipping_rates``. Failures log + return ``None``
(or empty list) so the caller can degrade gracefully without breaking
checkout / order flow.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger('morpheus.bookvault')


_AUTH_URL = 'https://auth.bookvault.app/api/WooAuth'
_SHIPPING_URL = 'https://webhooks.bookvault.app/woocommerce/shipping'
_ORDERS_URL = 'https://webhooks.bookvault.app/woocommerce/orders/create'
_PORTAL_ORDER_URL = 'https://portal.bookvault.app/order'
_BULK_PRODUCTS_URL = 'https://apps.bookvault.app/woocommerce/BulkProducts'
_TIMEOUT = 60


# ─── Config helpers ───────────────────────────────────────────────────────────


def _config() -> dict[str, Any]:
    """Pull the bookvault plugin's PluginConfig.config dict.

    Returns ``{}`` if the row doesn't exist yet — callers should
    treat that as "plugin not configured" and bail."""
    try:
        from plugins.models import PluginConfig
        cfg = PluginConfig.objects.filter(plugin_name='bookvault').first()
        return (cfg.config or {}) if cfg else {}
    except Exception as e:  # noqa: BLE001
        logger.warning('bookvault: PluginConfig lookup failed: %s', e)
        return {}


def _save_config(updates: dict[str, Any]) -> None:
    from plugins.models import PluginConfig
    cfg, _ = PluginConfig.objects.update_or_create(
        plugin_name='bookvault',
        defaults={'is_enabled': True},
    )
    merged = dict(cfg.config or {})
    merged.update(updates)
    cfg.config = merged
    cfg.save(update_fields=['config', 'updated_at'] if hasattr(cfg, 'updated_at') else ['config'])


def is_authenticated() -> bool:
    c = _config()
    return bool(c.get('authenticated') and c.get('token') and c.get('store_id'))


def store_url() -> str:
    """Best-effort canonical site URL for the BV auth handshake."""
    base = getattr(settings, 'MORPHEUS_SITE_URL', '') or ''
    if base:
        return base.rstrip('/') + '/'
    return ''


def currency() -> str:
    return (getattr(settings, 'MORPHEUS_DEFAULT_CURRENCY', '') or 'USD').upper()


# ─── Auth ─────────────────────────────────────────────────────────────────────


def authenticate(*, store_url_override: str = '') -> dict:
    """Mint a fresh BV token by GETting auth.bookvault.app/api/WooAuth.

    Persists ``token`` / ``store_id`` / ``authenticated`` into the
    plugin's config on success. Returns the raw BV response (or
    ``{'error': '…'}`` on failure)."""
    url = store_url_override.rstrip('/') + '/' if store_url_override else store_url()
    if not url:
        return {'error': 'no store URL configured; set MORPHEUS_SITE_URL'}
    try:
        resp = requests.get(_AUTH_URL, params={'storeUrl': url}, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
    except requests.RequestException as e:
        logger.warning('bookvault: auth handshake failed: %s', e)
        return {'error': str(e)}
    except ValueError:
        logger.warning('bookvault: auth response not JSON: %r', resp.text[:200])
        return {'error': 'BV auth response was not JSON'}

    token = (data or {}).get('Token') or ''
    sid = (data or {}).get('StoreID') or ''
    authed_flag = bool((data or {}).get('Authenticated'))
    if token and sid:
        _save_config({
            'token': token, 'store_id': str(sid),
            'authenticated': authed_flag,
        })
    return data


# ─── Shipping rates ───────────────────────────────────────────────────────────


def _isbn_lines(cart_or_order) -> list[dict]:
    """Extract ``[{ISBN, Quantity}]`` from a Cart or Order's items.

    BV only quotes lines whose SKU is exactly 13 chars — that's the
    ISBN-13 convention BV uses internally. Non-book lines are silently
    dropped, matching the WP plugin's behaviour."""
    lines: list[dict] = []
    items = getattr(cart_or_order, 'items', None)
    if items is None:
        return lines
    iterator = items.all() if hasattr(items, 'all') else items
    for item in iterator:
        variant = getattr(item, 'variant', None)
        sku = (getattr(variant, 'sku', '') or
               getattr(getattr(item, 'product', None), 'sku', '') or '')
        sku = (sku or '').strip()
        if len(sku) != 13:
            continue
        qty = int(getattr(item, 'quantity', 1) or 1)
        if qty < 1:
            continue
        lines.append({'ISBN': sku, 'Quantity': qty})
    return lines


def get_shipping_rates(
    *,
    cart=None,
    order_lines: list[dict] | None = None,
    country_code: str = '',
    postcode: str = '',
    service_level: str = 'NotSpecified',
) -> list[dict]:
    """POST to /woocommerce/shipping and return the list of services.

    ``order_lines`` is the explicit ``[{ISBN, Quantity}]`` list; pass
    ``cart`` instead to have us derive it from item SKUs. Returns
    ``[]`` if BV isn't configured, the request fails, or the cart has
    no ISBN lines."""
    if order_lines is None:
        if cart is None:
            return []
        order_lines = _isbn_lines(cart)
    if not order_lines or not country_code:
        return []

    payload = {
        'OrderLines': order_lines,
        'CountryCode': country_code.upper(),
        'ServiceLevel': service_level,
        'AreaCode': postcode or '',
    }
    params = {'storeUrl': store_url(), 'currency': currency()}
    try:
        resp = requests.post(
            _SHIPPING_URL, params=params, json=payload, timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
    except requests.RequestException as e:
        logger.warning('bookvault: shipping quote failed: %s', e)
        return []
    except ValueError:
        logger.warning('bookvault: shipping response not JSON: %r', resp.text[:200])
        return []
    services = (data or {}).get('Services') or []
    # Normalise field names so callers don't have to deal with PascalCase.
    out = []
    for s in services:
        try:
            out.append({
                'id': str(s.get('ServID') or ''),
                'name': s.get('ServName') or '',
                'detail': s.get('ServDetail') or '',
                'amount': Decimal(str(s.get('DelTotal') or '0')),
            })
        except (TypeError, ValueError):
            continue
    return out


# ─── Order forwarding ─────────────────────────────────────────────────────────


def _order_payload(order) -> dict:
    """Serialise an Order into the shape BV's /orders/create expects.

    The WP plugin sent WooCommerce's own ``$order->get_data()`` dict,
    which BV's webhook is built for. We approximate the same envelope
    so BV doesn't need a separate Morpheus mapping — it can stay on
    its WC parser."""
    items = []
    for item in order.items.all().select_related('product', 'variant'):
        variant = item.variant
        product = item.product
        sku = (getattr(variant, 'sku', '') or getattr(product, 'sku', '') or '')
        items.append({
            'product_id': str(getattr(product, 'id', '')),
            'variation_id': str(getattr(variant, 'id', '') or ''),
            'sku': sku,
            'name': getattr(product, 'name', ''),
            'quantity': int(item.quantity or 1),
            'price': str(getattr(item.unit_price, 'amount', 0)),
            'total': str(getattr(item.total_price, 'amount', 0)),
        })

    shipping = (getattr(order, 'shipping_address', None) or {}) or {}
    billing = (getattr(order, 'billing_address', None) or {}) or {}
    return {
        'id': str(order.id),
        'number': getattr(order, 'order_number', '') or str(order.id),
        'status': getattr(order, 'status', ''),
        'currency': str(getattr(order.total, 'currency', '') or 'USD'),
        'total': str(getattr(order.total, 'amount', 0)),
        'shipping': str(getattr(order.shipping_total, 'amount', 0)) if hasattr(order, 'shipping_total') else '',
        'line_items': items,
        'shipping_address': shipping,
        'billing_address': billing,
        'customer_email': (
            getattr(order, 'customer_email', '')
            or getattr(getattr(order, 'customer', None), 'email', '')
            or ''
        ),
        'date_created': order.created_at.isoformat() if getattr(order, 'created_at', None) else '',
    }


def send_order(*, order) -> dict:
    """POST a paid order to BV's /woocommerce/orders/create.

    Idempotent on resend: writes/updates a ``BookvaultOrderLink``, and
    captures the ``BVRef`` BV echoes back. Returns the BV response
    dict (or ``{'error': '…'}`` on failure).
    """
    from plugins.installed.bookvault.models import BookvaultOrderLink

    cfg = _config()
    if not (cfg.get('token') and cfg.get('store_id')):
        return {'error': 'BV not configured (missing token/store_id)'}
    if not cfg.get('auto_send_on_paid', True):
        # The hook fired but the merchant opted out — caller (the
        # ORDER_PAID handler) treats this as "not an error".
        return {'skipped': 'auto_send_on_paid disabled'}

    payload = _order_payload(order)
    params = {
        'client_id': cfg.get('token', ''),
        'storeID': cfg.get('store_id', ''),
    }
    try:
        resp = requests.post(
            _ORDERS_URL,
            params=params,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json() if resp.content else {}
    except requests.RequestException as e:
        logger.warning('bookvault: send_order order=%s failed: %s', order.id, e)
        return {'error': str(e)}
    except ValueError:
        body = {'raw': (resp.text or '')[:1000]}

    bv_ref = (
        (body or {}).get('BVRef')
        or (body or {}).get('OrderID')
        or (body or {}).get('ref')
        or ''
    )
    BookvaultOrderLink.objects.update_or_create(
        order=order,
        defaults={
            'bv_ref': str(bv_ref or ''),
            'last_response': body if isinstance(body, dict) else {'raw': str(body)},
        },
    )
    logger.info('bookvault: send_order order=%s bv_ref=%s', order.id, bv_ref or '(none)')
    return body


def portal_order_url(bv_ref: str) -> str:
    """Build the deep link the admin clicks to view the order in BV's portal."""
    if not bv_ref:
        return _PORTAL_ORDER_URL
    return f'{_PORTAL_ORDER_URL}?ID={bv_ref}'


def bulk_products_link(product_ids: list[str]) -> str:
    """Build the URL that hands product IDs off to BV's hosted Bulk
    Products linker. The merchant lands on BV's site, picks BV titles
    for each Morpheus product, and BV posts back via webhook."""
    cfg = _config()
    token = cfg.get('token', '')
    store_id = cfg.get('store_id', '')
    base = f'{_BULK_PRODUCTS_URL}?client_id={token}&storeID={store_id}'
    for pid in product_ids:
        base += f'&ids[]={pid}'
    return base


# ─── Link status helpers ──────────────────────────────────────────────────────


def product_link_status(product) -> str:
    """Aggregate status across a product's variants for the admin
    list column: 'Linked' / 'Partial' / 'Unlinked'."""
    from plugins.installed.bookvault.models import BookvaultProductLink

    has_linked = False
    has_unlinked = False
    variants = getattr(product, 'variants', None)
    variant_iter = list(variants.all()) if (variants is not None and hasattr(variants, 'all')) else []

    if variant_iter:
        for v in variant_iter:
            link = BookvaultProductLink.objects.filter(product=product, variant=v).first()
            if link and link.is_linked:
                has_linked = True
            else:
                has_unlinked = True
    else:
        link = BookvaultProductLink.objects.filter(product=product, variant__isnull=True).first()
        if link and link.is_linked:
            has_linked = True
        else:
            has_unlinked = True

    if has_linked and has_unlinked:
        return 'Partial'
    if has_linked:
        return 'Linked'
    return 'Unlinked'
