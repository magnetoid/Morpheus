"""MCP cart + checkout-quote tools — the buyer-agent surface.

These expose the SAME cart→session flow the REST ``/acp/`` endpoints use, as MCP
tools for the agent_mcp ``cart`` / ``checkout`` clusters. They REUSE the view
helpers verbatim — ``_get_cart`` (the IDOR + TTL-guarded session resolver),
``_add_line_items`` (eligibility check + ``CartService.add_item`` stock
reservation + localized pricing), ``_apply_buyer`` / ``_apply_fulfillment``, and
``_serialize`` (breakdown + totals + quoted-total stamp) — so there is exactly
zero duplicated money logic and no drift from the REST path.

COMPLETION (the actual charge) is deliberately NOT exposed here. It stays on the
mature ``complete_checkout_session`` REST endpoint behind all six money-path
gates (``payments_enabled`` default-off, quote-drift guard, ``select_for_update``
idempotency, Stripe-after-lock, …). An agent builds + quotes a cart over MCP,
then completes via ``/acp/`` — the "discover in AI, transact on the merchant's
own checkout" model. See docs/plans/ai-commerce-strategy-2026-2031.md (Phase 3).
"""

from __future__ import annotations

from typing import Any

from core.agents import ToolError, ToolResult, tool

_SESSION_SCHEMA = {
    'session_id': {
        'type': 'string',
        'description': 'The cart/checkout session id returned by cart.create.',
    }
}


def _resolve(session_id: Any):
    """Resolve a session id to its cart via the ACP resolver (IDOR + TTL guard)."""
    from plugins.installed.agentic_checkout.views import _get_cart

    cart = _get_cart(str(session_id or ''))
    if cart is None:
        raise ToolError('Unknown or expired cart session.')
    return cart


@tool(
    name='cart.create',
    description=(
        'Start a new agent shopping cart (checkout session) and return its id. '
        'Use cart.add_item to add products, then complete on the merchant checkout.'
    ),
    scopes=['cart.write'],
    schema={'type': 'object', 'properties': {}},
)
def cart_create_tool() -> ToolResult:
    from plugins.installed.agentic_checkout.views import _serialize
    from plugins.installed.orders.models import Cart

    cart = Cart.objects.create(metadata={'acp_session': True, 'source': 'mcp'})
    return ToolResult(output=_serialize(cart, None))


@tool(
    name='cart.add_item',
    description=(
        'Add a product to a cart session. Identify the product by `id` (its SKU, '
        'as advertised in the product feed) or by `product_id` / `variant_id`. '
        'Reserves stock and applies live pricing; returns the updated session '
        'with line items and running totals.'
    ),
    scopes=['cart.write'],
    schema={
        'type': 'object',
        'properties': {
            **_SESSION_SCHEMA,
            'id': {'type': 'string', 'description': 'Product/variant SKU (feed id).'},
            'product_id': {'type': 'string'},
            'variant_id': {'type': 'string'},
            'quantity': {'type': 'integer', 'minimum': 1, 'default': 1},
        },
        'required': ['session_id'],
    },
)
def cart_add_item_tool(
    *,
    session_id: str,
    id: str = '',  # noqa: A002 — matches the ACP line-item field name
    product_id: str = '',
    variant_id: str = '',
    quantity: int = 1,
) -> ToolResult:
    from plugins.installed.agentic_checkout.views import _add_line_items, _serialize

    cart = _resolve(session_id)
    line = {
        'id': id or '',
        'product_id': product_id or '',
        'variant_id': variant_id or '',
        'quantity': quantity,
    }
    messages = _add_line_items(cart, [line], currency=None)
    return ToolResult(output=_serialize(cart, None, extra_messages=messages))


@tool(
    name='cart.get',
    description='Read a cart session — its line items and running totals.',
    scopes=['cart.read'],
    schema={'type': 'object', 'properties': _SESSION_SCHEMA, 'required': ['session_id']},
)
def cart_get_tool(*, session_id: str) -> ToolResult:
    from plugins.installed.agentic_checkout.views import _serialize

    return ToolResult(output=_serialize(_resolve(session_id), None))


@tool(
    name='checkout.get_session',
    description=(
        'Read a checkout session — line items, buyer/fulfillment (if set), and '
        'totals (subtotal, and shipping + tax once an address is applied).'
    ),
    scopes=['cart.read'],
    schema={'type': 'object', 'properties': _SESSION_SCHEMA, 'required': ['session_id']},
)
def checkout_get_session_tool(*, session_id: str) -> ToolResult:
    from plugins.installed.agentic_checkout.views import _serialize

    return ToolResult(output=_serialize(_resolve(session_id), None))


@tool(
    name='checkout.set_buyer',
    description=(
        'Apply the buyer email + shipping address to a checkout session so the '
        'quote includes shipping and tax. Returns the updated session with full '
        'totals. Does NOT charge — completion happens on the merchant checkout.'
    ),
    scopes=['cart.write'],
    schema={
        'type': 'object',
        'properties': {
            **_SESSION_SCHEMA,
            'email': {'type': 'string'},
            'shipping_address': {
                'type': 'object',
                'description': (
                    'Address fields: name, line_one, line_two, city, state, '
                    'country (ISO-2), postal_code.'
                ),
            },
        },
        'required': ['session_id'],
    },
)
def checkout_set_buyer_tool(
    *,
    session_id: str,
    email: str = '',
    shipping_address: dict | None = None,
) -> ToolResult:
    from plugins.installed.agentic_checkout.views import (
        _apply_buyer,
        _apply_fulfillment,
        _serialize,
    )

    cart = _resolve(session_id)
    if email:
        _apply_buyer(cart, {'email': email})
    if isinstance(shipping_address, dict) and shipping_address:
        _apply_fulfillment(cart, {'email': email, 'address': shipping_address})
    return ToolResult(output=_serialize(cart, None))
