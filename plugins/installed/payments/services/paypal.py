"""PayPal REST integration (Orders v2 + Payments v2).

Plain ``requests`` against the REST API — no SDK dependency. Credentials come
from the payments plugin config (Settings → Payments): ``paypal_client_id``,
``paypal_client_secret`` (write-only), ``paypal_mode`` ('sandbox'|'live') and
``paypal_webhook_id``. The gateway is offered at checkout only when the
``paypal_enabled`` toggle projects ``PaymentGatewayConfig(slug='paypal')`` on —
mirroring the advanced_payments panel→config bridge.

Flow (redirect-based, unlike Stripe's client_secret):

    checkout → create_order() → shopper approves on PayPal → return view
    captures → mark_order_paid() (idempotent, fires ORDER_PAID once)

The PayPal *order id* is stored on ``PaymentTransaction.provider_transaction_id``
(the Stripe pattern: refunds look up the capture id at refund time via
``get_order()`` instead of persisting it — no schema change).
"""

# ruff: noqa: PLC0415
# Inline imports keep this importable before the app registry is ready.

from __future__ import annotations

import contextlib
import logging

import requests

logger = logging.getLogger('morpheus.payments.paypal')

_TIMEOUT = 15
_TOKEN_CACHE_KEY = 'paypal:access_token'


# ── Config ────────────────────────────────────────────────────────────────────


def get_config() -> dict:
    """PayPal credentials/mode from the payments plugin config (fail-soft)."""
    try:
        from plugins.registry import plugin_registry

        plugin = plugin_registry.get('payments')
        if plugin is None:
            return {}
        return {
            'client_id': str(plugin.get_config_value('paypal_client_id', '') or ''),
            'client_secret': str(plugin.get_config_value('paypal_client_secret', '') or ''),
            'mode': str(plugin.get_config_value('paypal_mode', 'sandbox') or 'sandbox'),
            'webhook_id': str(plugin.get_config_value('paypal_webhook_id', '') or ''),
            'enabled': bool(plugin.get_config_value('paypal_enabled', False)),
        }
    except Exception:  # noqa: BLE001
        return {}


def base_url() -> str:
    mode = get_config().get('mode', 'sandbox')
    return 'https://api-m.paypal.com' if mode == 'live' else 'https://api-m.sandbox.paypal.com'


def is_configured() -> bool:
    cfg = get_config()
    return bool(cfg.get('client_id') and cfg.get('client_secret'))


def sync_gateway_row(*args, **kwargs) -> None:
    """Project the ``paypal_enabled`` panel toggle onto PaymentGatewayConfig.

    ``enabled_gateways()`` reads PaymentGatewayConfig — not the plugin config —
    so the Settings → Payments toggle must be mirrored (same bridge the
    advanced_payments panel uses for cod/test).
    """
    try:
        from plugins.installed.payments.models import PaymentGatewayConfig

        cfg = get_config()
        enabled = bool(cfg.get('enabled')) and is_configured()
        PaymentGatewayConfig.objects.update_or_create(slug='paypal', defaults={'enabled': enabled})
    except Exception:  # noqa: BLE001 — never break a save/boot over the projection
        logger.warning('paypal: gateway config sync failed', exc_info=True)


# ── REST client ───────────────────────────────────────────────────────────────


def _access_token() -> str:
    """Client-credentials OAuth token, cached (~8h; PayPal issues 9h tokens)."""
    from django.core.cache import cache

    token = cache.get(_TOKEN_CACHE_KEY)
    if token:
        return token
    cfg = get_config()
    resp = requests.post(
        f'{base_url()}/v1/oauth2/token',
        auth=(cfg['client_id'], cfg['client_secret']),
        data={'grant_type': 'client_credentials'},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    payload = resp.json()
    token = payload['access_token']
    cache.set(_TOKEN_CACHE_KEY, token, min(int(payload.get('expires_in', 28800)) - 600, 28800))
    return token


def _headers() -> dict:
    return {
        'Authorization': f'Bearer {_access_token()}',
        'Content-Type': 'application/json',
    }


def create_order(order) -> dict:
    """Create a PayPal Order (intent=CAPTURE) for our Order.

    Returns ``{'success': True, 'paypal_order_id': ..., 'approval_url': ...}``
    or ``{'success': False, 'error': ...}``.
    """
    from core.utils.site import absolutize

    amount = order.total
    body = {
        'intent': 'CAPTURE',
        'purchase_units': [
            {
                'amount': {
                    'currency_code': amount.currency.code,
                    'value': f'{amount.amount:.2f}',
                },
                'custom_id': str(order.id),
                'invoice_id': order.order_number,
            }
        ],
        'payment_source': {
            'paypal': {
                'experience_context': {
                    'user_action': 'PAY_NOW',
                    'shipping_preference': 'NO_SHIPPING',
                    'return_url': absolutize('/payments/paypal/return/'),
                    'cancel_url': absolutize('/payments/paypal/cancel/'),
                }
            }
        },
    }
    try:
        resp = requests.post(
            f'{base_url()}/v2/checkout/orders',
            json=body,
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # noqa: BLE001 — surface as a retryable checkout error
        logger.warning('paypal: create order failed: %s', e)
        return {'success': False, 'error': f'PayPal order creation failed: {e}'[:300]}

    approval_url = ''
    for link in data.get('links', []):
        if link.get('rel') in ('payer-action', 'approve'):
            approval_url = link.get('href', '')
            break
    if not data.get('id') or not approval_url:
        return {'success': False, 'error': 'PayPal returned no approval link.'}
    return {'success': True, 'paypal_order_id': data['id'], 'approval_url': approval_url}


def capture_order(paypal_order_id: str) -> dict:
    """Capture an approved PayPal order. Returns {'success', 'capture_id'?, 'error'?}."""
    try:
        resp = requests.post(
            f'{base_url()}/v2/checkout/orders/{paypal_order_id}/capture',
            json={},
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        logger.warning('paypal: capture failed for %s: %s', paypal_order_id, e)
        return {'success': False, 'error': str(e)[:300]}

    if data.get('status') != 'COMPLETED':
        return {'success': False, 'error': f'capture status {data.get("status")}'}
    capture_id = ''
    with contextlib.suppress(KeyError, IndexError):
        capture_id = data['purchase_units'][0]['payments']['captures'][0]['id']
    return {'success': True, 'capture_id': capture_id}


def get_capture_id(paypal_order_id: str) -> str:
    """Look up the capture id on a completed PayPal order (for refunds)."""
    try:
        resp = requests.get(
            f'{base_url()}/v2/checkout/orders/{paypal_order_id}',
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data['purchase_units'][0]['payments']['captures'][0]['id']
    except Exception:  # noqa: BLE001
        return ''


def refund_capture(capture_id: str, amount) -> dict:
    """Refund a capture (partial when ``amount`` < captured total)."""
    body = {
        'amount': {
            'currency_code': amount.currency.code,
            'value': f'{amount.amount:.2f}',
        }
    }
    try:
        resp = requests.post(
            f'{base_url()}/v2/payments/captures/{capture_id}/refund',
            json=body,
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return {'success': True}
    except Exception as e:  # noqa: BLE001
        logger.warning('paypal: refund failed for %s: %s', capture_id, e)
        return {'success': False, 'error': str(e)[:300]}


def verify_webhook(headers, body: bytes) -> dict | None:
    """Verify a webhook delivery via PayPal's verify-webhook-signature API.

    Returns the parsed event dict on success, None on any verification failure.
    """
    import json

    cfg = get_config()
    webhook_id = cfg.get('webhook_id')
    if not webhook_id:
        logger.warning('paypal: webhook received but paypal_webhook_id is not configured')
        return None
    try:
        event = json.loads(body.decode('utf-8'))
        payload = {
            'auth_algo': headers.get('PAYPAL-AUTH-ALGO', ''),
            'cert_url': headers.get('PAYPAL-CERT-URL', ''),
            'transmission_id': headers.get('PAYPAL-TRANSMISSION-ID', ''),
            'transmission_sig': headers.get('PAYPAL-TRANSMISSION-SIG', ''),
            'transmission_time': headers.get('PAYPAL-TRANSMISSION-TIME', ''),
            'webhook_id': webhook_id,
            'webhook_event': event,
        }
        resp = requests.post(
            f'{base_url()}/v1/notifications/verify-webhook-signature',
            json=payload,
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        if resp.json().get('verification_status') == 'SUCCESS':
            return event
    except Exception as e:  # noqa: BLE001
        logger.warning('paypal: webhook verification failed: %s', e)
    return None


# ── Mark paid (idempotent — mirrors PaymentService._mark_transaction_success) ─


def mark_order_paid(paypal_order_id: str) -> bool:
    """Mark the transaction/order for this PayPal order paid, exactly once.

    Returns True when this call performed the transition (and fired
    ORDER_PAID), False when it was already processed or unknown.
    """
    from django.db import transaction as db_tx

    from core.hooks import MorpheusEvents, hook_registry
    from plugins.installed.payments.models import PaymentTransaction

    with db_tx.atomic():
        tx = (
            PaymentTransaction.objects.select_for_update()
            .filter(provider='paypal', provider_transaction_id=paypal_order_id)
            .first()
        )
        if not tx or tx.status == PaymentTransaction.Status.SUCCEEDED:
            return False

        tx.status = PaymentTransaction.Status.SUCCEEDED
        tx.save(update_fields=['status'])

        # Order.status is a protected FSMField — advance via confirm().
        order = tx.order
        order.payment_status = 'paid'
        if order.status == 'pending':
            order.confirm()
            order.save(update_fields=['payment_status', 'status'])
        else:
            order.save(update_fields=['payment_status'])

    # Fire AFTER commit so subscribers see the new row state.
    hook_registry.fire(MorpheusEvents.ORDER_PAID, order=order)
    return True
