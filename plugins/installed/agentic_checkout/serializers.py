"""ACP ``CheckoutSession`` serialization + money conversion.

Shapes mirror the real ACP ``2026-04-17`` ``openapi.agentic_checkout.yaml``:
``CheckoutSession`` (id, status, currency, line_items[], totals[],
fulfillment_options[], messages[], links[], created_at, updated_at) plus the
nested ``LineItem`` / ``Total`` / ``Item`` shapes and the ``MessageError`` /
``Message`` envelope.

Money: our ``djmoney.Money`` carries a Decimal **major-unit** amount;
ACP amounts are **integer minor units** (cents). We convert via the currency's
ISO-4217 minor-unit exponent (2 for USD/EUR, 0 for JPY/KRW, 3 for some Gulf
currencies). ``money_to_minor`` is the single conversion point — never multiply
by 100 inline.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

from django.http import JsonResponse

if TYPE_CHECKING:
    from djmoney.money import Money

# ── ACP CheckoutSession status enum (real spec) ───────────────────────────
STATUS_NOT_READY = 'not_ready_for_payment'
STATUS_READY = 'ready_for_payment'
STATUS_COMPLETED = 'completed'
STATUS_CANCELED = 'canceled'
STATUS_IN_PROGRESS = 'in_progress'

# Currencies whose minor unit is not 10^2. Anything not listed defaults to 2.
_MINOR_UNIT_EXPONENT: dict[str, int] = {
    'JPY': 0,
    'KRW': 0,
    'VND': 0,
    'CLP': 0,
    'ISK': 0,
    'HUF': 0,
    'BHD': 3,
    'KWD': 3,
    'OMR': 3,
    'TND': 3,
}


def minor_unit_exponent(currency: str) -> int:
    return _MINOR_UNIT_EXPONENT.get((currency or 'USD').upper(), 2)


def amount_to_minor(amount: Decimal, currency: str) -> int:
    """Decimal major units → integer minor units for ``currency``."""
    exp = minor_unit_exponent(currency)
    factor = Decimal(10) ** exp
    quantized = (Decimal(amount) * factor).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return int(quantized)


def money_to_minor(money: Money | None, fallback_currency: str = 'USD') -> int:
    """``Money`` → integer minor units. ``None`` → 0."""
    if money is None:
        return 0
    return amount_to_minor(Decimal(money.amount), str(money.currency) or fallback_currency)


def _total(total_type: str, display_text: str, amount: int) -> dict[str, Any]:
    """One ACP ``Total`` row."""
    return {'type': total_type, 'display_text': display_text, 'amount': amount}


def breakdown_to_totals(breakdown: dict, currency: str) -> list[dict[str, Any]]:
    """ACP ``totals[]`` from an ``OrderService.calculate_cart_breakdown`` dict.

    Emits only the rows that are present/non-trivial, always ending with
    ``total`` — matching the spec's ``Total`` ordering convention.
    """
    rows: list[dict[str, Any]] = []
    subtotal = breakdown.get('subtotal')
    shipping = breakdown.get('shipping')
    tax = breakdown.get('tax')
    discount = breakdown.get('discount')
    total = breakdown.get('total')

    if subtotal is not None:
        rows.append(_total('items_base_amount', 'Subtotal', money_to_minor(subtotal, currency)))
        rows.append(_total('subtotal', 'Subtotal', money_to_minor(subtotal, currency)))
    if discount is not None and money_to_minor(discount, currency) > 0:
        # Discounts are surfaced as a negative adjustment per ACP convention.
        rows.append(_total('discount', 'Discount', -money_to_minor(discount, currency)))
    if shipping is not None:
        rows.append(_total('fulfillment', 'Shipping', money_to_minor(shipping, currency)))
    if tax is not None:
        rows.append(_total('tax', 'Tax', money_to_minor(tax, currency)))
    if total is not None:
        rows.append(_total('total', 'Total', money_to_minor(total, currency)))
    return rows


def _availability_status(item) -> str:
    """ACP ``availability_status`` for a cart line.

    Reuses ``inventory.StockLevel.available_quantity`` (the same source
    ``google_shopping`` reads). No stock rows for the variant → treated as
    available (digital/untracked products have no ``StockLevel``).
    """
    variant = getattr(item, 'variant', None)
    if variant is None:
        return 'in_stock'
    try:
        from django.db.models import F, Sum

        from plugins.installed.inventory.models import StockLevel

        avail = StockLevel.objects.filter(variant=variant).aggregate(
            q=Sum(F('quantity') - F('reserved_quantity'))
        )['q']
    except Exception:  # noqa: BLE001 — no inventory plugin → assume available
        return 'in_stock'
    if avail is None:
        return 'in_stock'
    if avail <= 0:
        return 'out_of_stock'
    if avail < item.quantity:
        return 'low_stock'
    return 'in_stock'


def line_item_to_acp(item, currency: str) -> dict[str, Any]:
    """One ``CartItem`` → ACP ``LineItem``."""
    product = item.product
    variant = getattr(item, 'variant', None)
    name = product.name
    if variant is not None and getattr(variant, 'name', ''):
        name = f'{product.name} — {variant.name}'
    sku = (getattr(variant, 'sku', '') if variant is not None else '') or getattr(
        product, 'sku', ''
    )
    unit_minor = money_to_minor(item.unit_price, currency)
    line_minor = unit_minor * item.quantity
    return {
        'id': str(item.id),
        'item': {
            'id': sku or str(product.id),
            'name': name,
            'unit_amount': unit_minor,
        },
        'quantity': item.quantity,
        'sku': sku,
        'product_id': str(product.id),
        'variant_id': str(variant.id) if variant is not None else None,
        'availability_status': _availability_status(item),
        'totals': [
            _total('subtotal', 'Line subtotal', line_minor),
        ],
    }


def _links(request) -> list[dict[str, Any]]:
    """ACP ``links[]`` — terms / privacy / return policy from settings/CMS.

    Best-effort; absent pages simply omit their link rather than 404.
    """
    base = request.build_absolute_uri('/').rstrip('/') if request is not None else ''
    out: list[dict[str, Any]] = []
    for link_type, path in (
        ('terms_of_use', '/pages/terms/'),
        ('privacy_policy', '/pages/privacy/'),
        ('return_policy', '/pages/returns/'),
    ):
        out.append({'type': link_type, 'url': f'{base}{path}'})
    return out


def capabilities() -> dict[str, Any]:
    """ACP ``Capabilities`` (REQUIRED on every ``CheckoutSession``).

    Phase 1 advertises a single payment handler (Stripe Shared Payment Token)
    in the ``payment.handlers`` list. The handler is descriptive only — the
    money path is OFF until Phase 2, so ``complete`` returns ``unsupported``.
    """
    return {
        'payment': {
            'handlers': [
                {
                    'id': 'stripe_shared_payment_token',
                    'name': 'dev.acp.stripe.shared_payment_token',
                    'display_name': 'Card (Stripe Shared Payment Token)',
                }
            ]
        }
    }


def serialize_session(
    cart,
    *,
    status: str,
    breakdown: dict,
    request=None,
    messages: list[dict] | None = None,
) -> dict[str, Any]:
    """Build a conformant ACP ``CheckoutSession`` from a ``Cart``.

    The session ``id`` IS the ``Cart`` id (spec anchoring decision). ``status``
    is derived by the caller from cart/order state; ``breakdown`` comes from
    ``OrderService.calculate_cart_breakdown``.
    """
    items = list(cart.items.select_related('product', 'variant').all())
    currency = str(breakdown.get('currency') or 'USD')
    line_items = [line_item_to_acp(it, currency) for it in items]
    meta = cart.metadata or {}
    buyer = meta.get('acp_buyer') or None
    fulfillment = meta.get('acp_fulfillment') or None

    session: dict[str, Any] = {
        'id': str(cart.id),
        'status': status,
        'currency': currency,
        'line_items': line_items,
        'totals': breakdown_to_totals(breakdown, currency),
        'fulfillment_options': meta.get('acp_fulfillment_options') or [],
        'capabilities': capabilities(),
        'messages': messages or [],
        'links': _links(request),
        'created_at': cart.created_at.isoformat() if cart.created_at else None,
        'updated_at': cart.updated_at.isoformat() if cart.updated_at else None,
    }
    if buyer is not None:
        session['buyer'] = buyer
    if fulfillment is not None:
        session['fulfillment_details'] = fulfillment
    return session


def message_error(code: str, message: str, param: str = '') -> dict[str, Any]:
    """One ACP ``MessageError`` — ``type='error'`` + closed-enum ``code``.

    Per spec a ``MessageError`` carries ``type``, ``code`` (closed enum),
    ``content_type`` and ``content`` (the human text); there is no ``message``
    field.
    """
    out: dict[str, Any] = {
        'type': 'error',
        'code': code,
        'content_type': 'plain',
        'content': message,
    }
    if param:
        out['param'] = param
    return out


def message_info(message: str) -> dict[str, Any]:
    """One ACP ``MessageInfo`` — ``type='info'`` with NO ``code``."""
    return {'type': 'info', 'content_type': 'plain', 'content': message}


def error_response(code: str, message: str, *, status: int = 400) -> JsonResponse:
    """ACP top-level ``Error`` envelope (used for auth + request errors).

    Distinct from a ``MessageError`` embedded in a session — this is the
    request-level error body the spec returns with a 4xx status.
    """
    return JsonResponse(
        {'type': 'invalid_request', 'code': code, 'message': message},
        status=status,
    )
