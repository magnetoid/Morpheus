"""Single-page checkout — sprint priority #7.

Consolidates the 3-step flow (email/address → shipping → review) into
one scrollable page. The 3-step flow stays live at /checkout/ as a
fallback; the new flow lives at /checkout/quick/. Merchants can
A/B-test the two via the experiments plugin.

Why one-page wins for most shops:
  - Removes 2 navigation transitions; each one bleeds ~5% conversion.
  - All required info is visible up-front (no surprises late in the
    flow).
  - Mobile users can fill the entire form in a single thumb-scroll.

What we keep from the 3-step flow:
  - completeOrder GraphQL mutation — same backend.
  - Cart query, address fields, shipping-rate selection.
  - Stripe Payment Element on the redirect target (/checkout/payment/).

Guest-by-default: there is no "create account" gate before submission.
Authenticated users see a single "Save my info" checkbox at the
bottom of the form which links the order to their account.
"""

from __future__ import annotations

import logging
from typing import Any

from django.shortcuts import redirect, render

from api.client import internal_graphql
from plugins.installed.storefront.views._queries import CART_QUERY
from plugins.installed.storefront.views.checkout import (
    _available_shipping_rates,
    _cart_requires_shipping,
    _checkout_base_context,
)

logger = logging.getLogger('morpheus.storefront.checkout_one_page')


def _fire_begin_checkout(request) -> None:
    """Fire BEGIN_CHECKOUT once per session (same flag as the legacy 3-step
    flow, so switching flows can't double-fire). This is the LIVE path —
    cart_abandonment + analytics were blind on it. Fail-soft: analytics must
    never break checkout."""
    try:
        if request.session.get('checkout_started'):
            return
        from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415
        from plugins.installed.orders.models import Cart  # noqa: PLC0415

        cart_obj = None
        if request.user.is_authenticated:
            cart_obj = Cart.objects.filter(customer=request.user).first()
        elif request.session.session_key:
            cart_obj = Cart.objects.filter(session_key=request.session.session_key).first()
        if cart_obj is not None:
            hook_registry.fire(
                MorpheusEvents.BEGIN_CHECKOUT,
                cart=cart_obj,
                customer=request.user if request.user.is_authenticated else None,
                request=request,
            )
            request.session['checkout_started'] = True
    except Exception:  # noqa: BLE001
        logger.warning('BEGIN_CHECKOUT hook failed', exc_info=True)


def checkout_one_page(request):
    """Single-screen checkout — render or submit."""
    if request.method == 'GET':
        _fire_begin_checkout(request)
        return _render_form(request, addr=None, rate_id='', error='')

    addr = _collect_address(request)
    # Make GUEST carts reachable for abandonment recovery the moment an email
    # is typed — even if this submit later fails validation or payment.
    from .checkout import _stamp_checkout_email  # noqa: PLC0415

    _stamp_checkout_email(request, addr.get('email', ''))
    rate_id = (request.POST.get('shipping_rate_id') or '').strip()
    payment_method = (request.POST.get('payment_method') or '').strip()
    no_shipping = not _cart_requires_shipping(request)

    error = _validate(addr, no_shipping=no_shipping)
    if error:
        return _render_form(
            request, addr=addr, rate_id=rate_id, error=error, payment_method=payment_method
        )

    cart_data = internal_graphql(CART_QUERY, request=request) or {}
    cart = cart_data.get('cart') or {}

    # If shipping is required and no rate was selected, fall back to the
    # cheapest available rate.
    rates: list[dict[str, Any]] = []
    if not no_shipping:
        rates = _available_shipping_rates(request, addr)
        if rate_id and not any(str(r['id']) == rate_id for r in rates):
            rate_id = ''
        if not rate_id and rates:
            rate_id = str(rates[0]['id'])
    else:
        rate_id = 'no-shipping'

    cart_id = (cart.get('id') or request.session.get('cart_id') or '').strip()
    if not cart_id:
        return _render_form(
            request,
            addr=addr,
            rate_id=rate_id,
            error='Your cart has expired — add items again to continue.',
            payment_method=payment_method,
        )

    payload = _submit_order(
        request=request,
        cart_id=cart_id,
        addr=addr,
        rate_id=rate_id,
        payment_method=payment_method,
    )
    errs = payload.get('errors') or []
    if errs:
        return _render_form(
            request,
            addr=addr,
            rate_id=rate_id,
            error='; '.join(e.get('message', 'Order failed.') for e in errs),
            payment_method=payment_method,
        )

    order_no = payload.get('orderNumber') or ''
    client_secret = payload.get('paymentClientSecret') or ''
    request.session['checkout_order_number'] = order_no
    request.session['checkout_client_secret'] = client_secret
    for k in (
        'checkout_address',
        'checkout_shipping_rate_id',
        'checkout_shipping_rate_label',
    ):
        request.session.pop(k, None)

    if not client_secret:
        # No payment needed (free order / fully gift-carded). Send to
        # confirmation with public_token for guest access.
        return _redirect_to_confirmation(order_no)
    return redirect('/checkout/payment/')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_ADDRESS_FIELDS = (
    'email',
    'first_name',
    'last_name',
    'address_line1',
    'address_line2',
    'city',
    'state',
    'postal_code',
    'country',
    'phone',
)


def _collect_address(request) -> dict[str, str]:
    return {f: (request.POST.get(f) or '').strip() for f in _ADDRESS_FIELDS}


def _validate(addr: dict, *, no_shipping: bool) -> str:
    if not addr.get('email'):
        return 'Please enter your email address.'
    if no_shipping:
        return ''
    missing = [
        label
        for field, label in (
            ('address_line1', 'street address'),
            ('city', 'city'),
            ('country', 'country'),
        )
        if not addr.get(field)
    ]
    if missing:
        return f'Please fill in: {", ".join(missing)}.'
    return ''


def _shipping_input(addr: dict) -> dict:
    """Map the storefront address form to GraphQL ``AddressInput`` fields.

    NB: the input uses ``line1``/``line2`` (NOT ``addressLine1``/``2``) — see
    ``plugins/installed/orders/graphql/inputs.py``. Wrong names fail schema
    validation → 500 on checkout submit. Covered by a regression test.
    """
    return {
        'firstName': addr.get('first_name', ''),
        'lastName': addr.get('last_name', ''),
        'line1': addr.get('address_line1', ''),
        'line2': addr.get('address_line2', ''),
        'city': addr.get('city', ''),
        'state': addr.get('state', ''),
        'postalCode': addr.get('postal_code', ''),
        'country': addr.get('country', ''),
        'phone': addr.get('phone', ''),
    }


def _submit_order(
    *, request, cart_id: str, addr: dict, rate_id: str, payment_method: str = ''
) -> dict:
    mutation = """
    mutation Complete($input: CompleteOrderInput!) {
      completeOrder(input: $input) {
        orderNumber
        paymentClientSecret
        errors { code message }
      }
    }
    """
    shipping_input = _shipping_input(addr)
    data = (
        internal_graphql(
            mutation,
            variables={
                'input': {
                    'cartId': cart_id,
                    'email': addr.get('email', ''),
                    'shippingAddress': shipping_input,
                    'shippingRateId': rate_id if rate_id != 'no-shipping' else None,
                    # Server validates against enabled_gateways(); empty /
                    # unknown / disabled → default (stripe).
                    'paymentGateway': payment_method or None,
                },
            },
            request=request,
        )
        or {}
    )
    return data.get('completeOrder') or {}


def _redirect_to_confirmation(order_no: str):
    if not order_no:
        return redirect('/account/orders/')
    try:
        from plugins.installed.orders.models import Order  # noqa: PLC0415

        token = (
            Order.objects.filter(order_number=order_no)
            .values_list('public_token', flat=True)
            .first()
            or ''
        )
    except Exception:  # noqa: BLE001
        token = ''
    url = f'/order/confirmation/{order_no}/'
    if token:
        url = f'{url}?token={token}'
    return redirect(url)


def _render_form(request, *, addr: dict | None, rate_id: str, error: str, payment_method: str = ''):
    ctx = _checkout_base_context(request)
    ctx['no_shipping_required'] = not _cart_requires_shipping(request)
    ctx['form'] = addr or {}
    ctx['selected_rate_id'] = rate_id
    ctx['error'] = error
    ctx['payment_methods'] = _payment_methods()
    # Keep the shopper's pick across re-renders; default to the gateway the
    # picker flags as default (stripe) so the live path is pre-selected.
    if not payment_method:
        payment_method = next(
            (m['slug'] for m in ctx['payment_methods'] if m.get('is_default')), ''
        )
    ctx['selected_payment_method'] = payment_method
    if not ctx['no_shipping_required'] and addr:
        try:
            ctx['rates'] = _available_shipping_rates(request, addr)
        except Exception:  # noqa: BLE001
            ctx['rates'] = []
    else:
        ctx['rates'] = []
    return render(request, 'storefront/checkout_one_page.html', ctx)


def _payment_methods() -> list[dict]:
    """Enabled gateways for the checkout picker (fail-soft to [])."""
    try:
        from plugins.installed.payments.services.routing import picker_gateways  # noqa: PLC0415

        return picker_gateways()
    except Exception:  # noqa: BLE001 — never break checkout over the picker
        logger.warning('checkout: could not load payment methods', exc_info=True)
        return []
