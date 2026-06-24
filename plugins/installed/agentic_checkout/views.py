"""ACP checkout-session endpoints (agent-to-server, JSON, Bearer-auth).

These are programmatic API endpoints — CSRF-exempt because agents present a
Bearer token, not a browser session/cookie (same posture as the MCP server).
Every endpoint requires a valid token with the ``acp.checkout`` scope and
echoes the ``API-Version`` response header.

The session ``id`` IS a ``Cart`` id. ``createCheckoutSession`` builds a new
``Cart`` from ``line_items``; the others read/mutate/cancel/complete it.

Phase 1: ``complete`` returns a conformant ``CheckoutSession`` carrying a
``MessageError`` with code ``unsupported`` — the money path (Stripe Shared
Payment Token) is Phase 2.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from plugins.installed.agentic_checkout import serializers as ser
from plugins.installed.agentic_checkout.auth import require_acp_scope
from plugins.installed.agentic_checkout.plugin import ACP_API_VERSION

logger = logging.getLogger('morpheus.agentic_checkout')

# Upper bound on a single line item's quantity (defence against an agent
# sending an absurd number that would blow past stock + reservation math).
_MAX_QUANTITY = 1000
_DEFAULT_SESSION_TTL_MINUTES = 60


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


def _serialize(cart, request, *, extra_messages: list[dict] | None = None) -> dict:
    breakdown = _breakdown(cart)
    status = _derive_status(cart, breakdown)
    messages = _availability_messages(cart)
    if extra_messages:
        messages = messages + extra_messages
    return ser.serialize_session(
        cart,
        status=status,
        breakdown=breakdown,
        request=request,
        messages=messages,
    )


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


@csrf_exempt
@require_http_methods(['POST'])
def complete_checkout_session(request: HttpRequest, session_id: str) -> HttpResponse:
    """POST /acp/checkout_sessions/{id}/complete — Phase 2 (money path).

    Returns a conformant ``CheckoutSession`` carrying a ``MessageError`` with
    code ``unsupported``. The Stripe Shared Payment Token redemption is NOT
    implemented in Phase 1.

    A 200 on this route implies ``CheckoutSessionWithOrder`` (i.e. a real
    ``order``). Because Phase 1 creates no order we return the session under a
    422 so an agent can never read it as a successful completion.
    """
    denied = require_acp_scope(request)
    if denied is not None:
        return _with_version(denied)

    cart = _get_cart(session_id)
    if cart is None:
        return _with_version(
            ser.error_response('not_found', 'Checkout session not found.', status=404)
        )

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
