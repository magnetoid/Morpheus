"""Express checkout from the cart: Apple Pay, Google Pay and Link through Stripe's
Express Checkout Element, before the shopper fills in the checkout form.

The wallet sheet shows an amount before any order exists, and Stripe charges the
PaymentIntent's amount, so the two must be the same number. Every amount here comes
from ``OrderService.calculate_cart_breakdown`` for the address the wallet shares,
the call ``create_from_cart`` makes with the same address, and the order is placed
only while the amount the sheet showed still holds. The order itself goes through
``completeOrder``, the mutation both checkout forms use.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.utils.countries import normalise_country, store_country
from plugins.installed.payments.services.money import amount_to_minor

logger = logging.getLogger('morpheus.payments.express')

#: The wallet fields an address keeps, capped like the order's own address fields.
_ADDRESS_LIMIT = 255


def _setting(key: str, default):
    from plugins.registry import app_registry  # noqa: PLC0415

    return app_registry.config_value('payments', key, default)


def _item_ships(item) -> bool:
    target = item.variant if item.variant is not None else item.product
    return bool(getattr(target, 'requires_shipping', True))


def session_cart(request):
    """The visitor's own cart with items, or None when there is nothing to buy."""
    from plugins.installed.orders.models import Cart  # noqa: PLC0415

    cart_id = request.session.get('cart_id') if hasattr(request, 'session') else None
    if not cart_id:
        return None
    try:
        cart = (
            Cart.objects.filter(id=cart_id)
            .prefetch_related('items__product', 'items__variant')
            .first()
        )
    except (ValueError, TypeError):
        return None
    if cart is None or not cart.items.all():
        return None
    return cart


def cart_ships(cart) -> bool:
    """Whether the cart needs a delivery address (the checkout forms' own rule)."""
    from plugins.registry import app_registry  # noqa: PLC0415

    if app_registry.config_value('orders', 'skip_shipping_for_digital_carts', True) is False:
        return True
    return any(_item_ships(item) for item in cart.items.all())


def needs_waiver(cart) -> bool:
    """A digital item with the withdrawal waiver on: only the checkout form can take
    the shopper's tick, so the wallet buttons stay off for this cart."""
    from plugins.registry import app_registry  # noqa: PLC0415

    if not app_registry.config_value('orders', 'digital_withdrawal_waiver_enabled', False):
        return False
    return any(not _item_ships(item) for item in cart.items.all())


def form_only(cart, user=None) -> bool:
    """Whether only the checkout form can place this order: the withdrawal waiver, a
    required checkout field (the terms tick, core/checkout_fields.py), or a store that
    takes no guest orders and a shopper who is not signed in."""
    from core.checkout_fields import has_required  # noqa: PLC0415
    from plugins.installed.orders.checkout_fields import guest_checkout_allowed  # noqa: PLC0415

    if needs_waiver(cart) or has_required(user=user):
        return True
    return not guest_checkout_allowed() and not getattr(user, 'is_authenticated', False)


def stripe_ready(user=None) -> bool:
    """Stripe is switched on and set up, the rule the checkout picker uses."""
    from plugins.installed.payments.gateway import gateway_registry  # noqa: PLC0415

    try:
        return any(g.slug == 'stripe' for g in gateway_registry.enabled_gateways(user=user))
    except Exception:  # noqa: BLE001 — no buttons rather than a broken cart page
        logger.warning('express: could not list gateways', exc_info=True)
        return False


def _currency(cart) -> str:
    return str(cart.items.all()[0].unit_price.currency)


def _split_name(name: str) -> tuple[str, str]:
    parts = (name or '').split()
    if len(parts) < 2:
        return (parts[0] if parts else ''), ''
    return ' '.join(parts[:-1]), parts[-1]


def wallet_address(raw, *, name: str = '', phone: str = '') -> dict:
    """A wallet's address in the shape ``completeOrder`` stores (``_address_dict``)."""
    raw = raw if isinstance(raw, dict) else {}
    first, last = _split_name(str(name or ''))

    def text(key: str) -> str:
        return str(raw.get(key) or '').strip()[:_ADDRESS_LIMIT]

    return {
        'first_name': first[:_ADDRESS_LIMIT],
        'last_name': last[:_ADDRESS_LIMIT],
        'line1': text('line1'),
        'line2': text('line2'),
        'city': text('city'),
        'state': text('state'),
        'postal_code': text('postal_code'),
        'country': normalise_country(raw.get('country')),
        'phone': str(phone or '').strip()[:50],
    }


def _rates(cart, address: dict, currency: str) -> list[dict]:
    """The checkout's shipping choices for an address, in this cart's currency.

    Mirrors the checkout forms: when no shipping app answers, delivery is free.
    """
    from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415

    rates = hook_registry.filter(
        MorpheusEvents.CHECKOUT_SHIPPING_RATES, None, cart=cart, address=address
    )
    if rates is None:
        rates = [{'id': 'standard', 'label': _('Standard delivery'), 'amount': 0}]
    out = []
    for rate in rates or []:
        if str(rate.get('currency') or currency).upper() != currency.upper():
            continue
        try:
            amount = amount_to_minor(Decimal(str(rate.get('amount') or 0)), currency)
        except (InvalidOperation, TypeError, ValueError):
            continue
        out.append(
            {
                'id': str(rate['id']),
                'displayName': str(rate.get('label') or rate['id'])[:100],
                'amount': amount,
            }
        )
    return out


def quote(cart, address: dict, rate_id: str = '') -> dict:
    """What the wallet sheet shows for one address: shipping choices and the total.

    ``rateId`` is the choice the total is for: the one asked for while it is on
    offer, else the first. Amounts are Stripe's minor units.
    """
    from plugins.installed.orders.services import OrderService  # noqa: PLC0415

    currency = _currency(cart)
    rates: list[dict] = []
    rate_id = str(rate_id or '')
    if cart_ships(cart):
        rates = _rates(cart, address, currency)
        if rates and not any(r['id'] == rate_id for r in rates):
            rate_id = rates[0]['id']
        if not rates:
            rate_id = ''
    else:
        rate_id = ''
    # completeOrder bills the shipping address when the wallet sends no other, and
    # create_from_cart prices with both: the same pair here gives the same total.
    breakdown = OrderService.calculate_cart_breakdown(
        cart=cart, address=address, billing_address=address, shipping_rate_id=rate_id
    )
    total = breakdown['total']
    return {
        'amount': amount_to_minor(total.amount, currency),
        'currency': currency.lower(),
        'shippingRates': rates,
        'rateId': rate_id,
    }


def cart_offer(request) -> dict:
    """The cart page's wallet buttons, or {} when the store cannot offer them."""
    from plugins.installed.payments.services.stripe import PaymentService  # noqa: PLC0415

    if request is None or not _setting('express_on_cart', True):
        return {}
    if not stripe_ready(user=getattr(request, 'user', None)):
        return {}
    cart = session_cart(request)
    key = PaymentService.get_stripe_public_key()
    if cart is None or form_only(cart, getattr(request, 'user', None)) or not key:
        return {}
    try:
        offer = quote(cart, {'country': store_country()})
    except Exception:  # noqa: BLE001 — the cart page keeps its own checkout button
        logger.warning('express: could not price the cart', exc_info=True)
        return {}
    ships = cart_ships(cart)
    if offer['amount'] <= 0 or (ships and not offer['shippingRates']):
        return {}
    from plugins.installed.payments.services.capture import cart_mode  # noqa: PLC0415

    # The sheet must ask Stripe for the same capture as the payment the order
    # will start (capture_mode): a held card for every mode but immediate.
    held = cart_mode(all(_item_ships(i) for i in cart.items.all())) != 'immediate'
    return {
        'config': {
            'key': key,
            'amount': offer['amount'],
            'currency': offer['currency'],
            'captureMethod': 'manual' if held else 'automatic',
            'ships': ships,
            'shippingRates': offer['shippingRates'],
            'rateId': offer['rateId'],
            'quoteUrl': reverse('payments:express_quote'),
            'orderUrl': reverse('payments:express_order'),
            'payUrl': '/checkout/payment/',
            'text': {
                'failed': _('The payment did not go through. Try again, or check out below.'),
                'payAnotherWay': _('Pay another way'),
            },
        }
    }


def _json(request) -> dict:
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _refuse(message: str, status: int = 409, **extra) -> JsonResponse:
    return JsonResponse({'error': message, 'message': message, **extra}, status=status)


@require_POST
def express_quote(request):
    """POST /payments/express/quote/ — shipping choices and the total for an address."""
    cart = session_cart(request)
    if cart is None:
        return _refuse(_('Your cart is empty.'), status=404)
    data = _json(request)
    address = wallet_address(data.get('address'))
    try:
        result = quote(cart, address, str(data.get('rateId') or ''))
    except Exception:  # noqa: BLE001 — the wallet reports the address as unserviceable
        logger.warning('express: quote failed', exc_info=True)
        return _refuse(_('We could not price delivery to this address.'))
    if cart_ships(cart) and not result['shippingRates']:
        return _refuse(_('We do not deliver to this address.'))
    return JsonResponse(result)


def _confirmation_url(request, order_number: str) -> str:
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    token = (
        Order.objects.filter(order_number=order_number)
        .values_list('public_token', flat=True)
        .first()
        or ''
    )
    path = f'/order/confirmation/{order_number}/'
    if token:
        path = f'{path}?token={token}'
    return request.build_absolute_uri(path)


def _shopper(cart, data: dict) -> tuple[str, dict, str]:
    """Email and address from the wallet's confirm event, and what is missing ('' if nothing).

    A cart that ships is delivered to the wallet's shipping address; a digital one
    is billed to its billing address (tax on a download follows the buyer).
    """
    billing = data.get('billingDetails') if isinstance(data.get('billingDetails'), dict) else {}
    email = str(billing.get('email') or '').strip()[:254]
    if '@' not in email:
        return email, {}, _('A valid email is required.')
    if not cart_ships(cart):
        address = wallet_address(
            billing.get('address'),
            name=str(billing.get('name') or ''),
            phone=str(billing.get('phone') or ''),
        )
        return email, address, ''
    shipping = data.get('shippingAddress') if isinstance(data.get('shippingAddress'), dict) else {}
    address = wallet_address(
        shipping.get('address'),
        name=str(shipping.get('name') or billing.get('name') or ''),
        phone=str(billing.get('phone') or ''),
    )
    if not (address['line1'] and address['city'] and address['country']):
        return email, address, _('Please choose a full delivery address.')
    return email, address, ''


def _still_shown(cart, data: dict, result: dict) -> str:
    """'' when the sheet showed this total and delivery choice, else why not."""
    if cart_ships(cart) and result['rateId'] != str(data.get('rateId') or ''):
        return _('That delivery option is no longer available. Please choose again.')
    try:
        shown = int(data.get('amount'))
    except (TypeError, ValueError):
        shown = None
    if shown != result['amount']:
        return _('The total changed for this address. Please check it and pay again.')
    return ''


def _complete(request, cart, email: str, address: dict, rate_id: str) -> dict:
    """``completeOrder`` with Stripe, the mutation both checkout forms place orders with."""
    from api.client import internal_graphql  # noqa: PLC0415

    mutation = """
    mutation Complete($input: CompleteOrderInput!) {
      completeOrder(input: $input) {
        orderNumber
        paymentClientSecret
        errors { code message }
      }
    }
    """
    data = internal_graphql(
        mutation,
        variables={
            'input': {
                'cartId': str(cart.id),
                'email': email,
                'shippingAddress': {
                    'firstName': address['first_name'],
                    'lastName': address['last_name'],
                    'line1': address['line1'],
                    'line2': address['line2'],
                    'city': address['city'],
                    'state': address['state'],
                    'postalCode': address['postal_code'],
                    'country': address['country'],
                    'phone': address['phone'],
                },
                'shippingRateId': rate_id or None,
                'paymentGateway': 'stripe',
            }
        },
        request=request,
    )
    return (data or {}).get('completeOrder') or {}


def _charged(order_number: str):
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    order = Order.objects.filter(order_number=order_number).first()
    if order is None:
        return None
    return amount_to_minor(order.total.amount, str(order.total.currency))


@require_POST
def express_order(request):
    """POST /payments/express/order/ — place the order the wallet sheet showed.

    Refuses with the new amount when the total for the wallet's address is not the
    amount the sheet showed, so the shopper is never charged a number they did not
    see. A placed order leaves the cart, so a declined wallet payment carries on at
    the checkout's payment step.
    """
    cart = session_cart(request)
    if cart is None:
        return _refuse(_('Your cart is empty.'), status=404)
    user = getattr(request, 'user', None)
    if not stripe_ready(user=user) or form_only(cart, user):
        return _refuse(_('Please check out below.'))
    data = _json(request)
    email, address, problem = _shopper(cart, data)
    result = {}
    if not problem:
        try:
            result = quote(cart, address, str(data.get('rateId') or ''))
        except Exception:  # noqa: BLE001 — refused like an address it cannot price
            logger.warning('express: quote failed', exc_info=True)
            problem = _('We could not price delivery to this address.')
        else:
            # Nothing to charge (a gift card covers it) has no wallet payment to take.
            if result['amount'] > 0:
                problem = _still_shown(cart, data, result)
            else:
                problem = _('Please check out below.')
    if problem:
        # The new total goes back, so the sheet can show it on the next try.
        return _refuse(problem, **({'amount': result['amount']} if result else {}))

    payload = _complete(request, cart, email, address, result['rateId'])
    errors = payload.get('errors') or []
    order_number = payload.get('orderNumber') or ''
    if errors or not order_number:
        message = '; '.join(str(e.get('message') or '') for e in errors)
        return _refuse(message or _('The order could not be placed.'))
    charged = _charged(order_number)
    if charged != result['amount']:
        # Never charge a number the sheet did not show: no client secret goes back,
        # and the unpaid order expires like any abandoned one.
        logger.error(
            'express: order %s totals %s, the sheet showed %s',
            order_number,
            charged,
            result['amount'],
        )
        return _refuse(_('The order could not be placed.'))

    client_secret = payload.get('paymentClientSecret') or ''
    # The checkout's payment step reads these, so a declined wallet can pay another way.
    request.session['checkout_order_number'] = order_number
    request.session['checkout_client_secret'] = client_secret
    return JsonResponse(
        {
            'orderNumber': order_number,
            'clientSecret': client_secret,
            'returnUrl': _confirmation_url(request, order_number),
        }
    )
