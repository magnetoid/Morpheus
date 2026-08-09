"""ACP checkout-session endpoints (agent-to-server, JSON, Bearer-auth).

These are programmatic API endpoints — CSRF-exempt because agents present a
Bearer token, not a browser session/cookie (same posture as the MCP server).
Every endpoint requires a valid token with the ``acp.checkout`` scope and
echoes the ``API-Version`` response header.

The session ``id`` IS a ``Cart`` id. ``createCheckoutSession`` builds a new
``Cart`` from ``line_items``; the others read/mutate/cancel/complete it.

``complete`` is the money path (Phase 2), gated on the ``payments_enabled``
config flag: it places a real ``Order`` and redeems the Stripe Shared Payment
Token off-session through the payments plugin. With the flag off (or the
payments plugin unavailable) it returns a conformant ``CheckoutSession``
carrying a ``MessageError`` with code ``unsupported`` — the Phase-1 behavior.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from plugins.installed.agentic_checkout import serializers as ser
from plugins.installed.agentic_checkout.auth import _bearer_token, require_acp_scope
from plugins.installed.agentic_checkout.eligibility import agentic_excluded
from plugins.installed.agentic_checkout.plugin import ACP_API_VERSION

logger = logging.getLogger('morpheus.agentic_checkout')

# Upper bound on a single line item's quantity (defence against an agent
# sending an absurd number that would blow past stock + reservation math).
_MAX_QUANTITY = 1000
_DEFAULT_SESSION_TTL_MINUTES = 60
# How long a `complete` in-flight claim (metadata['acp_completing']) blocks
# concurrent completions before it is presumed dead and taken over.
_CLAIM_TTL = timedelta(minutes=10)


# ── helpers ───────────────────────────────────────────────────────────────


def _with_version(response: HttpResponse) -> HttpResponse:
    response['API-Version'] = ACP_API_VERSION
    return response


def _json_body(request: HttpRequest) -> dict[str, Any] | None:
    try:
        data = json.loads(request.body or b'{}')
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _session_ttl_minutes() -> int:
    """Session lifetime from plugin config (``session_ttl_minutes``)."""
    try:
        from plugins.models import PluginConfig

        row = PluginConfig.objects.filter(plugin_name='agentic_checkout').first()
        if row and isinstance(row.config, dict):
            ttl = row.config.get('session_ttl_minutes')
            if isinstance(ttl, int) and ttl > 0:
                return ttl
    except Exception:  # noqa: BLE001, S110 — config read is best-effort
        pass
    return _DEFAULT_SESSION_TTL_MINUTES


def _payments_enabled() -> bool:
    """Money-path opt-in from plugin config (``payments_enabled``, default off)."""
    try:
        from plugins.models import PluginConfig

        row = PluginConfig.objects.filter(plugin_name='agentic_checkout').first()
        if row and isinstance(row.config, dict):
            return bool(row.config.get('payments_enabled'))
    except Exception:  # noqa: BLE001, S110 — config read is best-effort
        pass
    return False


def _get_cart(session_id: str):
    """Load an ACP-owned cart by session id, or ``None``.

    SECURITY: only carts created through this surface carry the
    ``metadata['acp_session']`` marker. Filtering on it means an
    ``acp.checkout`` token can never read or mutate an ordinary storefront
    cart (PII, addresses, reservations) by guessing its id — and the caller
    returns 404 (not 403) so there is no existence oracle. Sessions older
    than the configured TTL are treated as not found (expired).
    """
    from plugins.installed.orders.models import Cart

    cart = Cart.objects.filter(id=session_id, metadata__acp_session=True).first()
    if cart is None:
        return None
    if cart.updated_at is not None:
        age = timezone.now() - cart.updated_at
        if age > timedelta(minutes=_session_ttl_minutes()):
            return None
    return cart


def _breakdown(cart):
    from plugins.installed.orders.services import OrderService

    meta = cart.metadata or {}
    address = meta.get('acp_fulfillment', {}).get('address') if isinstance(meta, dict) else None
    return OrderService.calculate_cart_breakdown(
        cart=cart,
        address=address or None,
        shipping_rate_id=str(meta.get('shipping_rate_id') or ''),
    )


def _derive_status(cart, breakdown) -> str:
    """ACP status from cart state.

    Empty cart → not_ready_for_payment. Has items + a buyer email + a
    fulfillment address → ready_for_payment. Otherwise (priced but missing
    buyer/address) → not_ready_for_payment.
    """
    if not cart.items.exists():
        return ser.STATUS_NOT_READY
    meta = cart.metadata or {}
    buyer = meta.get('acp_buyer') or {}
    fulfillment = meta.get('acp_fulfillment') or {}
    has_buyer = bool(buyer.get('email'))
    has_address = bool(fulfillment.get('address'))
    total = breakdown.get('total')
    has_total = total is not None and total.amount > 0
    if has_buyer and has_address and has_total:
        return ser.STATUS_READY
    return ser.STATUS_NOT_READY


def _availability_messages(cart) -> list[dict]:
    """Surface out_of_stock / low_stock as ACP messages on the session."""
    messages: list[dict] = []
    for item in cart.items.select_related('product', 'variant').all():
        status = ser._availability_status(item)
        if status == 'out_of_stock':
            messages.append(
                ser.message_error('out_of_stock', f'{item.product.name} is out of stock.')
            )
        elif status == 'low_stock':
            messages.append(ser.message_info(f'Limited stock remaining for {item.product.name}.'))
    return messages


def _stamp_quoted_total(cart, breakdown) -> None:
    """Persist the minor-units total this response advertises.

    ``complete`` compares the stamp against a fresh recompute and refuses to
    charge a drifted amount (price edit, promo expiry, tax/shipping recalc
    between quote and completion) — the agent must re-fetch first.
    """
    total = breakdown.get('total')
    if total is None:
        return
    quoted = ser.money_to_minor(total, str(breakdown.get('currency') or 'USD'))
    meta = cart.metadata if isinstance(cart.metadata, dict) else {}
    if meta.get('acp_quoted_total') == quoted:
        return
    meta = dict(meta)
    meta['acp_quoted_total'] = quoted
    cart.metadata = meta
    # No `updated_at` — advertising a quote must not extend the session TTL.
    cart.save(update_fields=['metadata'])


def _serialize(
    cart,
    request,
    *,
    extra_messages: list[dict] | None = None,
    breakdown: dict | None = None,
) -> dict:
    if breakdown is None:
        breakdown = _breakdown(cart)
    status = _derive_status(cart, breakdown)
    messages = _availability_messages(cart)
    if extra_messages:
        messages = messages + extra_messages
    session = ser.serialize_session(
        cart,
        status=status,
        breakdown=breakdown,
        request=request,
        messages=messages,
    )
    _stamp_quoted_total(cart, breakdown)
    return session


def _apply_buyer(cart, buyer: dict | None) -> None:
    if not isinstance(buyer, dict):
        return
    meta = dict(cart.metadata or {})
    meta['acp_buyer'] = {
        'email': str(buyer.get('email') or ''),
        'first_name': str(buyer.get('first_name') or ''),
        'last_name': str(buyer.get('last_name') or ''),
        'phone': str(buyer.get('phone') or ''),
    }
    cart.metadata = meta
    cart.save(update_fields=['metadata', 'updated_at'])


_ADDRESS_FIELDS = (
    'name',
    'line_one',
    'line_two',
    'city',
    'state',
    'country',
    'postal_code',
)


def _apply_fulfillment(cart, fulfillment: dict | None) -> None:
    """Persist only the whitelisted, bounded ``FulfillmentDetails`` fields.

    Storing the agent payload verbatim would let an agent stash arbitrary
    keys/sizes in cart metadata; we keep just the spec's contact + address
    fields, each truncated.
    """
    if not isinstance(fulfillment, dict):
        return

    def _s(val: Any) -> str:
        return str(val or '')[:256]

    clean: dict[str, Any] = {
        'name': _s(fulfillment.get('name')),
        'phone_number': _s(fulfillment.get('phone_number')),
        'email': _s(fulfillment.get('email')),
    }
    addr = fulfillment.get('address')
    if isinstance(addr, dict):
        clean['address'] = {k: _s(addr.get(k)) for k in _ADDRESS_FIELDS if addr.get(k)}
    meta = dict(cart.metadata or {})
    meta['acp_fulfillment'] = clean
    cart.metadata = meta
    cart.save(update_fields=['metadata', 'updated_at'])


def _valid_currency(currency: str | None) -> bool:
    """``True`` iff ``currency`` is a known ISO-4217 code (or unset)."""
    if not currency:
        return True
    from moneyed import CURRENCIES

    return str(currency).upper() in CURRENCIES


def _parse_quantity(raw: Any) -> int | None:
    """Parse + clamp a quantity. ``None`` means invalid (non-numeric / < 1)."""
    try:
        qty = int(raw) if raw is not None else 1
    except (TypeError, ValueError):
        return None
    if qty < 1:
        return None
    return min(qty, _MAX_QUANTITY)


def _resolve_line_items(line_items: list) -> tuple[list[dict], list[dict]]:
    """Validate ACP ``line_items`` WITHOUT mutating the cart.

    Per the create-request schema each element is an ``Item`` with ``id`` and
    ``quantity`` directly on it (nested ``item`` kept only as a fallback).
    Returns ``(resolved, messages)`` where ``resolved`` is a list of
    ``{product, variant, quantity}`` ready to add, and ``messages`` are
    per-item ``MessageError``s (bad quantity / unknown product). Validating
    before any delete/add lets the UPDATE path reject bad input without
    emptying the cart.
    """
    from plugins.installed.catalog.models import Product, ProductVariant

    resolved: list[dict] = []
    messages: list[dict] = []
    for li in line_items or []:
        if not isinstance(li, dict):
            continue
        item = li.get('item') if isinstance(li.get('item'), dict) else {}
        # Schema shape: id/quantity directly on the element; nested item is a
        # legacy fallback only.
        ref = li.get('id') or item.get('id')
        raw_qty = li.get('quantity') if li.get('quantity') is not None else item.get('quantity')
        product_id = li.get('product_id') or item.get('product_id')
        variant_id = li.get('variant_id') or item.get('variant_id')
        ref = ref or product_id or variant_id

        quantity = _parse_quantity(raw_qty)
        if quantity is None:
            messages.append(
                ser.message_error('invalid', f'Invalid quantity for {ref!r}.', param='line_items')
            )
            continue

        product = None
        variant = None
        if variant_id:
            variant = ProductVariant.objects.filter(id=variant_id).first()
            if variant is not None:
                product = variant.product
        if product is None and product_id:
            product = Product.objects.filter(id=product_id).first()
        if product is None and ref:
            # Resolve by SKU (the id we advertise in the feed + item.id).
            variant = ProductVariant.objects.filter(sku=ref).first()
            if variant is not None:
                product = variant.product
            else:
                product = Product.objects.filter(sku=ref).first()

        if product is None:
            messages.append(
                ser.message_error('not_found', f'No product for {ref!r}.', param='line_items')
            )
            continue
        if agentic_excluded(product):
            messages.append(
                ser.message_error(
                    'invalid',
                    f'{product.name} is not available for agent checkout.',
                    param='line_items',
                )
            )
            continue
        resolved.append({'product': product, 'variant': variant, 'quantity': quantity})
    return resolved, messages


def _apply_line_items(cart, resolved: list[dict], currency: str | None) -> list[dict]:
    """Add already-validated line items to the cart; collect any add errors."""
    from plugins.installed.orders.services import CartService

    messages: list[dict] = []
    for entry in resolved:
        product = entry['product']
        variant = entry['variant']
        try:
            CartService.add_item(
                cart,
                str(product.id),
                quantity=entry['quantity'],
                variant_id=str(variant.id) if variant is not None else None,
                currency=currency,
            )
        except ValueError as e:
            messages.append(ser.message_error('out_of_stock', str(e), param='line_items'))
    return messages


def _add_line_items(cart, line_items: list, currency: str | None) -> list[dict]:
    """Validate + add ACP ``line_items`` to the cart (create path)."""
    resolved, messages = _resolve_line_items(line_items)
    messages += _apply_line_items(cart, resolved, currency)
    return messages


# ── endpoints ─────────────────────────────────────────────────────────────


@csrf_exempt
@require_http_methods(['POST'])
def create_checkout_session(request: HttpRequest) -> HttpResponse:
    """POST /acp/checkout_sessions — new Cart from line_items + currency."""
    denied = require_acp_scope(request)
    if denied is not None:
        return _with_version(denied)

    body = _json_body(request)
    if body is None:
        return _with_version(ser.error_response('invalid_body', 'Request body must be JSON.'))

    from plugins.installed.orders.models import Cart

    currency = body.get('currency')
    messages: list[dict] = []
    if not _valid_currency(currency):
        messages.append(
            ser.message_error('invalid', f'Unknown currency {currency!r}.', param='currency')
        )
        currency = None

    # Stamp the ACP-session marker at creation so _get_cart can tell this cart
    # apart from an ordinary storefront cart (IDOR guard).
    cart = Cart.objects.create(metadata={'acp_session': True})
    messages += _add_line_items(cart, body.get('line_items') or [], currency)
    _apply_buyer(cart, body.get('buyer'))
    fulfillment = body.get('fulfillment_details') or body.get('fulfillment')
    _apply_fulfillment(cart, fulfillment)

    session = _serialize(cart, request, extra_messages=messages)
    return _with_version(JsonResponse(session, status=201))


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def checkout_session_detail(request: HttpRequest, session_id: str) -> HttpResponse:
    """GET → read; POST → update (line items / fulfillment / buyer)."""
    denied = require_acp_scope(request)
    if denied is not None:
        return _with_version(denied)

    cart = _get_cart(session_id)
    if cart is None:
        return _with_version(
            ser.error_response('not_found', 'Checkout session not found.', status=404)
        )

    if request.method == 'GET':
        return _with_version(JsonResponse(_serialize(cart, request)))

    body = _json_body(request)
    if body is None:
        return _with_version(ser.error_response('invalid_body', 'Request body must be JSON.'))

    messages: list[dict] = []
    currency = body.get('currency')
    if 'line_items' in body:
        if not _valid_currency(currency):
            messages.append(
                ser.message_error('invalid', f'Unknown currency {currency!r}.', param='currency')
            )
            currency = None
        # Validate the FULL line_items payload BEFORE touching the cart: a bad
        # quantity or unknown product must not silently empty the existing cart.
        resolved, parse_messages = _resolve_line_items(body.get('line_items') or [])
        messages += parse_messages
        if resolved or not parse_messages:
            # Replace contents only when we have a usable set (or an explicitly
            # empty list). If every item failed to parse, keep the old cart.
            cart.items.all().delete()
            messages += _apply_line_items(cart, resolved, currency)
    if 'buyer' in body:
        _apply_buyer(cart, body.get('buyer'))
    fulfillment = body.get('fulfillment_details') or body.get('fulfillment')
    if fulfillment is not None:
        _apply_fulfillment(cart, fulfillment)

    return _with_version(JsonResponse(_serialize(cart, request, extra_messages=messages)))


@csrf_exempt
@require_http_methods(['POST'])
def cancel_checkout_session(request: HttpRequest, session_id: str) -> HttpResponse:
    """POST /acp/checkout_sessions/{id}/cancel — release the cart, status canceled."""
    denied = require_acp_scope(request)
    if denied is not None:
        return _with_version(denied)

    cart = _get_cart(session_id)
    if cart is None:
        return _with_version(
            ser.error_response('not_found', 'Checkout session not found.', status=404)
        )

    # Release any cart-time stock reservations, then empty the cart.
    try:
        from plugins.installed.inventory.cart_reservations import release_cart

        release_cart(str(cart.id))
    except Exception:  # noqa: BLE001 — reservation release is best-effort
        logger.debug('agentic_checkout: reservation release failed for cart %s', cart.id)

    cart.items.all().delete()
    breakdown = _breakdown(cart)
    session = ser.serialize_session(
        cart,
        status=ser.STATUS_CANCELED,
        breakdown=breakdown,
        request=request,
        messages=[ser.message_info('Checkout session canceled.')],
    )
    return _with_version(JsonResponse(session))


def _order_block(order, cart, request: HttpRequest | None) -> dict[str, Any]:
    """ACP ``Order`` object for a ``CheckoutSessionWithOrder`` response."""
    permalink = f'/order/confirmation/{order.order_number}/'
    if request is not None:
        permalink = request.build_absolute_uri(permalink)
    return {
        'id': str(order.id),
        'checkout_session_id': str(cart.id),
        'permalink_url': permalink,
    }


def _order_line_items(order, currency: str) -> list[dict[str, Any]]:
    """ACP ``line_items[]`` rebuilt from persisted ``OrderItem`` rows.

    ``create_from_cart`` empties the cart, so an idempotent retry (or a
    pending-order response) can't serialize cart items — the Order snapshot
    is the source of truth for what was purchased.
    """
    items: list[dict[str, Any]] = []
    for oi in order.items.all():
        name = oi.product_name
        if oi.variant_name:
            name = f'{oi.product_name} — {oi.variant_name}'
        items.append(
            {
                'id': str(oi.id),
                'item': {
                    'id': oi.sku or str(oi.product_id or ''),
                    'name': name,
                    'unit_amount': ser.money_to_minor(oi.unit_price, currency),
                },
                'quantity': oi.quantity,
                'sku': oi.sku,
                'product_id': str(oi.product_id) if oi.product_id else None,
                'variant_id': str(oi.variant_id) if oi.variant_id else None,
                'availability_status': 'in_stock',
                'totals': [
                    {
                        'type': 'subtotal',
                        'display_text': 'Line subtotal',
                        'amount': ser.money_to_minor(oi.total_price, currency),
                    }
                ],
            }
        )
    return items


def _order_snapshot(order, cart, request: HttpRequest | None, *, status: str) -> dict[str, Any]:
    """Session body rebuilt from a persisted ``Order`` (the cart is empty)."""
    currency = str(order.total.currency)
    breakdown = {
        'currency': currency,
        'subtotal': order.subtotal,
        'shipping': order.shipping_total,
        'tax': order.tax_total,
        'discount': order.discount_total,
        'total': order.total,
    }
    session = ser.serialize_session(cart, status=status, breakdown=breakdown, request=request)
    session['line_items'] = _order_line_items(order, currency)
    return session


def _claim_fresh(meta: dict) -> bool:
    """``True`` iff an in-flight completion claim younger than the TTL exists."""
    raw = str(meta.get('acp_completing') or '')
    if not raw:
        return False
    claimed_at = parse_datetime(raw)
    if claimed_at is None:
        return False
    if timezone.is_naive(claimed_at):
        claimed_at = timezone.make_aware(claimed_at)
    return timezone.now() - claimed_at < _CLAIM_TTL


def _clear_claim(cart) -> None:
    """Release the in-flight claim so the agent can retry this session.

    ``acp_pending_order_id`` is kept — the retry reuses that order, and the
    session-scoped Stripe idempotency key makes the re-redeem replay-safe.
    """
    meta = dict(cart.metadata) if isinstance(cart.metadata, dict) else {}
    if 'acp_completing' not in meta:
        return
    meta.pop('acp_completing', None)
    cart.metadata = meta
    cart.save(update_fields=['metadata', 'updated_at'])


def _quote_drift_error(cart, breakdown) -> dict | None:
    """MessageError when the total drifted since it was quoted, else ``None``."""
    meta = cart.metadata if isinstance(cart.metadata, dict) else {}
    quoted = meta.get('acp_quoted_total')
    if quoted is None:
        return None
    current = ser.money_to_minor(breakdown.get('total'), str(breakdown.get('currency') or 'USD'))
    try:
        if int(quoted) == current:
            return None
    except (TypeError, ValueError):
        return None
    return ser.message_error(
        'invalid',
        'Session total changed — re-fetch the checkout session before completing.',
        param='total',
    )


def _record_delegation_evidence(order, cart, request: HttpRequest, token: str) -> None:
    """Dispute evidence on the Order via the metafields plugin (zero-migration).

    Fail-soft: metafields disabled/absent (or any write hiccup) must never
    poison the success path of an already-charged order.
    """
    try:
        from plugins.installed.metafields.models import Metafield

        Metafield.objects.set(
            order,
            namespace='acp',
            key='evidence',
            value={
                'api_version': ACP_API_VERSION,
                'session_id': str(cart.id),
                'token_fingerprint': hashlib.sha256(_bearer_token(request).encode()).hexdigest()[
                    :16
                ],
                'spt_last4': token[-4:],
                'completed_at': timezone.now().isoformat(),
                'user_agent': str(request.META.get('HTTP_USER_AGENT', ''))[:300],
            },
        )
    except Exception:  # noqa: BLE001 — evidence is best-effort
        logger.warning(
            'agentic_checkout: evidence metafield write failed for order %s',
            getattr(order, 'pk', '?'),
        )


def _unsupported_response(cart, request: HttpRequest) -> HttpResponse:
    """The Phase-1 conformant ``unsupported`` 422 (money path off)."""
    session = _serialize(
        cart,
        request,
        extra_messages=[
            ser.message_error(
                'unsupported',
                'Agentic Commerce Protocol completion (Shared Payment Token) is '
                'not yet enabled on this store.',
            )
        ],
    )
    return _with_version(JsonResponse(session, status=422))


def _payment_service():
    """The payments plugin's ``PaymentService``, or ``None`` when unavailable."""
    try:
        from plugins.installed.payments.services.stripe import PaymentService
    except ImportError:
        return None
    return PaymentService


def _completion_contact(cart) -> tuple[str, dict | None]:
    """(email, shipping_address) accumulated on the cart by ``update`` calls."""
    meta = cart.metadata if isinstance(cart.metadata, dict) else {}
    buyer = meta.get('acp_buyer') or {}
    fulfillment = meta.get('acp_fulfillment') or {}
    email = str(buyer.get('email') or fulfillment.get('email') or '').strip()
    address = fulfillment.get('address')
    if not isinstance(address, dict) or not address:
        address = None
    return email, address


def _missing_messages(cart, email: str, address: dict | None) -> list[dict]:
    """Param-scoped ``missing`` MessageErrors for an incomplete session."""
    missing: list[dict] = []
    if not cart.items.exists():
        missing.append(
            ser.message_error('missing', 'Checkout session has no line items.', param='line_items')
        )
    if not email:
        missing.append(
            ser.message_error(
                'missing', 'A buyer email is required to complete checkout.', param='buyer.email'
            )
        )
    if address is None:
        missing.append(
            ser.message_error(
                'missing',
                'A shipping address is required to complete checkout.',
                param='fulfillment_details.address',
            )
        )
    return missing


def _payment_data_error(body: dict) -> tuple[str, dict | None]:
    """Validate ``payment_data`` → (token, MessageError-or-None)."""
    payment = body.get('payment_data') if isinstance(body.get('payment_data'), dict) else {}
    provider = str(payment.get('provider') or '').strip().lower()
    token = str(payment.get('token') or '').strip()
    if provider != 'stripe':
        return token, ser.message_error(
            'unsupported',
            f'Unsupported payment provider {provider!r} — only "stripe" '
            '(Shared Payment Token) is accepted.',
            param='payment_data.provider',
        )
    if not token:
        return token, ser.message_error(
            'invalid',
            'payment_data.token must be a non-empty Shared Payment Token.',
            param='payment_data.token',
        )
    return token, None


def _finalize_paid_order(order, cart, request: HttpRequest, token: str) -> None:
    """Success path — mirror the Stripe webhook's ``_mark_transaction_success``.

    Flip ``payment_status``, run the ``confirm()`` FSM transition, fire
    ORDER_PAID, record delegation evidence, and swap the in-flight claim for
    the ``acp_order_id`` stamp so an agent retry of ``complete`` returns this
    order instead of charging again.
    """
    from morpheus.core import MorpheusEvents, hook_registry

    order.payment_status = 'paid'
    order.source = 'agent:acp'
    if order.status == 'pending':
        order.confirm()
        order.save(update_fields=['payment_status', 'status', 'source'])
    else:
        order.save(update_fields=['payment_status', 'source'])
    hook_registry.fire(MorpheusEvents.ORDER_PAID, order=order)

    _record_delegation_evidence(order, cart, request, token)

    stamped = {
        k: v
        for k, v in dict(cart.metadata or {}).items()
        if k not in ('acp_completing', 'acp_pending_order_id')
    }
    stamped['acp_order_id'] = str(order.id)
    cart.metadata = stamped
    cart.save(update_fields=['metadata', 'updated_at'])


def _create_order_for_completion(cart, request: HttpRequest):
    """Validate the session + place the ``Order`` (inside the locked txn).

    Returns ``(error_response, order, session_snapshot)`` — exactly one of
    ``error_response`` / ``order`` is set.
    """
    from plugins.installed.orders.services import OrderService

    email, address = _completion_contact(cart)
    missing = _missing_messages(cart, email, address)
    if missing:
        return (
            JsonResponse(_serialize(cart, request, extra_messages=missing), status=422),
            None,
            None,
        )

    # Quote-drift guard: never charge a total the agent hasn't seen. The 422
    # body re-advertises (and re-stamps) the current totals — it IS the
    # re-fetch the message asks for.
    breakdown = _breakdown(cart)
    drift = _quote_drift_error(cart, breakdown)
    if drift is not None:
        body = _serialize(cart, request, breakdown=breakdown, extra_messages=[drift])
        return JsonResponse(body, status=422), None, None

    # Snapshot the priced session BEFORE create_from_cart empties the cart so
    # the completed/declined response still carries the purchased line items.
    session = _serialize(cart, request, breakdown=breakdown)
    try:
        order = OrderService.create_from_cart(
            cart,
            email,
            address,
            address,
            # Agent checkouts rarely carry the storefront visitor cookie, but
            # stamp it when present so experiments can attribute the purchase.
            visitor_id=(request.COOKIES.get('morph_visitor') or '').strip(),
        )
    except ValueError as e:
        msg = ser.message_error('invalid', str(e))
        return (
            JsonResponse(_serialize(cart, request, extra_messages=[msg]), status=422),
            None,
            None,
        )
    return None, order, session


def _locked_complete(request: HttpRequest, session_id: str, body: dict):
    """The claim/idempotency gate + order creation, under the cart row lock.

    Runs inside ``transaction.atomic()`` with the cart re-fetched via
    ``select_for_update`` so two concurrent ``complete`` calls serialize:
    the loser then sees either the winner's ``acp_order_id`` stamp (→ 200
    idempotent retry) or its fresh ``acp_completing`` claim (→ 409-style
    conflict). Returns ``(early_response, ctx)``; ``ctx`` is
    ``(cart, order, token, session_snapshot)`` when redemption should
    proceed — the Stripe call itself happens AFTER the lock is released.
    """
    from plugins.installed.orders.models import Cart, Order

    cart = (
        Cart.objects.select_for_update().filter(id=session_id, metadata__acp_session=True).first()
    )
    if cart is None:
        return ser.error_response('not_found', 'Checkout session not found.', status=404), None

    meta = cart.metadata if isinstance(cart.metadata, dict) else {}

    # (a) Already completed → the same order, never a second charge.
    if meta.get('acp_order_id'):
        existing = Order.objects.filter(id=meta['acp_order_id']).first()
        if existing is not None:
            session = _order_snapshot(existing, cart, request, status=ser.STATUS_COMPLETED)
            session['order'] = _order_block(existing, cart, request)
            return JsonResponse(session), None

    # (b) Another completion is in flight → conflict; stale claims (crashed
    # worker) are taken over below.
    if _claim_fresh(meta):
        conflict = _serialize(
            cart,
            request,
            extra_messages=[
                ser.message_error('invalid', 'Completion already in progress — retry shortly.')
            ],
        )
        # Spec fidelity: an in-flight completion is 'in_progress', not the
        # ready/not_ready _derive_status would otherwise emit (ACP status enum).
        conflict['status'] = ser.STATUS_IN_PROGRESS
        return JsonResponse(conflict, status=409), None

    token, payment_error = _payment_data_error(body)
    if payment_error is not None:
        body_ = _serialize(cart, request, extra_messages=[payment_error])
        return JsonResponse(body_, status=422), None

    # (c) Reuse the pending order from an interrupted attempt (the cart is
    # already empty; the session-scoped idempotency key replays the charge),
    # else validate + create one now.
    order = None
    if meta.get('acp_pending_order_id'):
        order = Order.objects.filter(id=meta['acp_pending_order_id']).first()
    if order is not None:
        session = _order_snapshot(order, cart, request, status=ser.STATUS_READY)
    else:
        error, order, session = _create_order_for_completion(cart, request)
        if error is not None:
            return error, None

    # Claim the session before COMMIT so concurrent completes see it.
    claimed = dict(cart.metadata or {})
    claimed['acp_completing'] = timezone.now().isoformat()
    claimed['acp_pending_order_id'] = str(order.id)
    cart.metadata = claimed
    cart.save(update_fields=['metadata', 'updated_at'])

    return None, (cart, order, token, session)


def _payment_failure_message(result: dict) -> dict:
    """Map a redeem failure dict onto a conformant ``MessageError``.

    Retryable outcomes (connection interrupted, intent still processing)
    come back as ``invalid`` so the agent retries the SAME session; hard
    declines are ``payment_declined`` with ``param`` naming the offending
    request field and the Stripe decline code folded into the content.
    """
    error = str(result.get('error') or 'Payment was declined.')
    if result.get('retryable'):
        return ser.message_error('invalid', error)
    code = str(result.get('decline_code') or '')
    content = f'{error} (decline code: {code})' if code else error
    return ser.message_error('payment_declined', content, param='payment_data.token')


@csrf_exempt
@require_http_methods(['POST'])
def complete_checkout_session(  # noqa: PLR0911 — validation ladder, one exit per error
    request: HttpRequest, session_id: str
) -> HttpResponse:
    """POST /acp/checkout_sessions/{id}/complete — the money path (Phase 2).

    Gated on plugin config ``payments_enabled`` + the payments plugin being
    importable; otherwise the Phase-1 conformant ``unsupported`` 422 is
    preserved. The idempotency gate + order creation run inside a
    ``select_for_update`` transaction (see ``_locked_complete``): a retry on
    an already-completed session returns the same order (200), a concurrent
    completion gets a 409-style conflict, and a drifted total is refused
    before any charge. The Stripe redeem happens AFTER the lock is released
    — never hold a DB lock across a network call. On success the order is
    confirmed the same way the Stripe webhook success path does (ORDER_PAID
    fires) and delegation evidence is recorded; on decline or a retryable
    interruption the claim is cleared so the agent can retry the session
    (the session-scoped Stripe idempotency key makes the replay safe).
    """
    denied = require_acp_scope(request)
    if denied is not None:
        return _with_version(denied)

    cart = _get_cart(session_id)
    if cart is None:
        return _with_version(
            ser.error_response('not_found', 'Checkout session not found.', status=404)
        )

    payment_service = _payment_service() if _payments_enabled() else None
    if payment_service is None:
        return _unsupported_response(cart, request)

    body = _json_body(request)
    if body is None:
        return _with_version(ser.error_response('invalid_body', 'Request body must be JSON.'))

    with transaction.atomic():
        early, ctx = _locked_complete(request, str(cart.id), body)
    if early is not None:
        return _with_version(early)
    cart, order, token, session = ctx

    # The ACP session id rides on the PaymentIntent metadata and keys the
    # session-scoped idempotency. Order has no metadata DB column — this is
    # an instance attr redeem reads fail-soft.
    order.metadata = {'acp': {'session_id': str(cart.id)}}
    result = payment_service.redeem_delegated_token(order, token)

    if not result.get('success'):
        # Mirror the webhook failure convention: any FAILED/PENDING
        # PaymentTransaction is already recorded by redeem; the order stays
        # pending/unpaid. Release the claim so the session can retry.
        _clear_claim(cart)
        session['messages'] = list(session.get('messages') or []) + [
            _payment_failure_message(result)
        ]
        return _with_version(JsonResponse(session, status=422))

    _finalize_paid_order(order, cart, request, token)

    session['status'] = ser.STATUS_COMPLETED
    session['order'] = _order_block(order, cart, request)
    return _with_version(JsonResponse(session))
