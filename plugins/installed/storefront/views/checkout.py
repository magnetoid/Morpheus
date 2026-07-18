"""Server-rendered 4-step checkout: contact/address → shipping rate →
review → Stripe payment. Plus gift card apply/remove side-trips.
"""

# ruff: noqa: PLC0415, I001, S110, S112, PLR0911, PLR0912, PLR5501
# Inline imports keep checkout import-light + avoid plugin load-order
# coupling; the guarded try/except blocks degrade gracefully so a wedged
# optional plugin (shipping, gift cards) never breaks the checkout flow.

from __future__ import annotations

import logging

from api.client import internal_graphql
from morpheus.views import redirect, render

from ._queries import CART_QUERY

logger = logging.getLogger('morpheus.storefront.checkout')


def _cart_requires_shipping(request) -> bool:
    """Returns True if any cart item needs a shipping address. Digital /
    virtual carts skip the shipping-address step + rate picker."""
    try:
        from plugins.registry import plugin_registry

        plugin = None
        for attr in ('get', 'get_plugin'):
            fn = getattr(plugin_registry, attr, None)
            if callable(fn):
                try:
                    plugin = fn('orders')
                except Exception:  # noqa: BLE001
                    continue
                if plugin is not None:
                    break
        if plugin is not None:
            cfg = plugin.get_config() or {}
            if cfg.get('skip_shipping_for_digital_carts') is False:
                return True
    except Exception:  # noqa: BLE001
        pass

    try:
        from plugins.installed.orders.models import Cart

        cart_id = request.session.get('cart_id')
        if not cart_id:
            return True
        cart = (
            Cart.objects.filter(id=cart_id)
            .prefetch_related('items__product', 'items__variant')
            .first()
        )
        if cart is None or not cart.items.all():
            return True
        for item in cart.items.all():
            if item.variant is not None:
                if getattr(item.variant, 'requires_shipping', True):
                    return True
            else:
                if getattr(item.product, 'requires_shipping', True):
                    return True
        return False
    except Exception:  # noqa: BLE001
        return True


def _cart_has_digital(request) -> bool:
    """True if the cart contains at least one downloadable/digital item
    (``requires_shipping=False``). Unlike ``_cart_requires_shipping`` (which
    is False only for an all-digital cart), this catches a MIXED cart too —
    the EU withdrawal-waiver applies whenever any digital item is present."""
    try:
        from plugins.installed.orders.models import Cart

        cart_id = request.session.get('cart_id')
        if not cart_id:
            return False
        cart = (
            Cart.objects.filter(id=cart_id)
            .prefetch_related('items__product', 'items__variant')
            .first()
        )
        if cart is None:
            return False
        for item in cart.items.all():
            target = item.variant if item.variant is not None else item.product
            if not getattr(target, 'requires_shipping', True):
                return True
        return False
    except Exception:  # noqa: BLE001
        return False


def _withdrawal_waiver() -> dict:
    """Merchant-configured digital withdrawal-waiver: ``{enabled, text}``.
    Off by default (the merchant enables it once the wording is finalised);
    falls back to the schema defaults so checkout never breaks on config."""
    enabled, text = False, ''
    try:
        from plugins.registry import plugin_registry

        plugin = plugin_registry.get('orders')
        if plugin is not None:
            enabled = bool(plugin.get_config_value('digital_withdrawal_waiver_enabled', False))
            text = str(plugin.get_config_value('digital_withdrawal_waiver_text', '') or '')
    except Exception:  # noqa: BLE001
        enabled, text = False, ''
    if not text:
        text = (
            'I expressly request immediate access to the digital content in my '
            'order, and I acknowledge that I thereby lose my 14-day right of '
            'withdrawal once the download or streaming begins.'
        )
    return {'enabled': enabled, 'text': text}


def waiver_gate(request) -> str:
    """'' unless the cart needs the digital withdrawal-waiver and the POST
    didn't tick it. Shared by both checkout paths."""
    waiver = _withdrawal_waiver()
    needed = waiver['enabled'] and _cart_has_digital(request)
    if needed and request.POST.get('digital_withdrawal_waiver') != '1':
        return 'Please confirm the digital-content acknowledgement to continue.'
    return ''


def record_waiver(order_no: str) -> None:
    """Stamp the accepted digital withdrawal-waiver onto the order (exact text
    shown + timestamp) — the compliance artifact. Uses QuerySet.update to skip
    the protected FSM status field; fail-soft, no-op on empty order_no."""
    if not order_no:
        return
    try:
        from django.utils import timezone

        from plugins.installed.orders.models import Order

        order = Order.objects.filter(order_number=order_no).first()
        if order is None:
            return
        meta = dict(order.metadata or {})
        meta['digital_withdrawal_waiver'] = {
            'accepted': True,
            'text': _withdrawal_waiver()['text'],
            'at': timezone.now().isoformat(),
        }
        Order.objects.filter(pk=order.pk).update(metadata=meta)
    except Exception as e:  # noqa: BLE001 — never break the confirmation redirect
        import logging

        logging.getLogger('morpheus.storefront.checkout').warning(
            'checkout: withdrawal-waiver record failed for %s: %s', order_no, e
        )


def _checkout_base_context(request):
    """Common context for every checkout step — cart summary + prefill."""
    cart_data = internal_graphql(CART_QUERY, request=request) or {}
    saved = request.session.get('checkout_address') or {}
    user = getattr(request, 'user', None)
    if not saved and user is not None and getattr(user, 'is_authenticated', False):
        saved = {
            'email': getattr(user, 'email', '') or '',
            'first_name': getattr(user, 'first_name', '') or '',
            'last_name': getattr(user, 'last_name', '') or '',
        }
        try:
            addr = (
                user.addresses.filter(address_type__in=('shipping', 'both'))
                .order_by('-is_default', '-updated_at', '-created_at')
                .first()
            )
            if addr is not None:
                saved.update(
                    {
                        'first_name': saved.get('first_name') or addr.first_name or '',
                        'last_name': saved.get('last_name') or addr.last_name or '',
                        'address_line1': addr.address_line1 or '',
                        'address_line2': addr.address_line2 or '',
                        'city': addr.city or '',
                        'state': addr.state or '',
                        'postal_code': addr.postal_code or '',
                        'country': addr.country or 'US',
                        'phone': addr.phone or '',
                    }
                )
        except Exception:  # noqa: BLE001
            pass
    cart = cart_data.get('cart') or {}
    return {
        'cart': cart,
        'totals': _cart_totals(request, cart),
        'form': saved,
    }


def _cart_totals(request, cart: dict) -> dict:
    """Real breakdown (discount/shipping/tax/total) for the summary rows.
    Empty dict on any failure — templates fall back to subtotal-only."""
    cart_id = (cart.get('id') or request.session.get('cart_id') or '').strip()
    if not cart_id:
        return {}
    try:
        from ._queries import CART_TOTALS_QUERY

        data = internal_graphql(CART_TOTALS_QUERY, variables={'cartId': cart_id}, request=request)
        totals = (data or {}).get('cartTotals') or {}
        # Drop zero rows so templates never render a "$0.00 Shipping/Tax/
        # Discount" line (e.g. before an address is entered).
        for key in ('discount', 'shipping', 'tax'):
            try:
                if float((totals.get(key) or {}).get('amount') or 0) == 0:
                    totals.pop(key, None)
            except (TypeError, ValueError):
                totals.pop(key, None)
        return totals
    except Exception:  # noqa: BLE001 — summary rows are progressive enhancement
        return {}


def _stamp_checkout_email(request, email: str) -> None:
    """Persist the checkout-entered email onto the visitor's cart metadata.

    This is what makes GUEST carts recoverable: the cart-abandonment drip
    reads ``metadata['checkout_email']`` when the cart has no customer
    account. Consent is still checked at send time — stamping the address
    only makes the cart *reachable*, never mailable by itself. Fail-soft:
    a stamp failure must never affect checkout.
    """
    email = (email or '').strip()
    if not email or '@' not in email:
        return
    try:
        from plugins.installed.orders.models import Cart  # noqa: PLC0415

        if request.user.is_authenticated:
            cart = Cart.objects.filter(customer=request.user).order_by('-updated_at').first()
        elif request.session.session_key:
            cart = (
                Cart.objects.filter(session_key=request.session.session_key)
                .order_by('-updated_at')
                .first()
            )
        else:
            cart = None
        if cart is None:
            return
        meta = dict(cart.metadata or {})
        if meta.get('checkout_email') != email:
            meta['checkout_email'] = email
            cart.metadata = meta
            cart.save(update_fields=['metadata'])
    except Exception:  # noqa: BLE001
        logger.warning('checkout: email stamp failed', exc_info=True)


def _available_shipping_rates(request, addr):
    """Rate options via the CHECKOUT_SHIPPING_RATES filter (shipping plugin).

    The shipping plugin subscribes and returns normalized rate dicts. When no
    rate owner answers — plugin disabled, absent, or its handler broke — the
    value stays None and checkout falls back to free standard delivery, so
    the flow never blocks on the plugin.
    """
    from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415
    from plugins.installed.orders.models import Cart  # noqa: PLC0415

    cart_id = request.session.get('cart_id')
    cart = Cart.objects.filter(id=cart_id).first() if cart_id else None
    if cart is None:
        return []
    rates = hook_registry.filter(
        MorpheusEvents.CHECKOUT_SHIPPING_RATES, None, cart=cart, address=addr
    )
    if rates is None:
        return [{'id': 'standard', 'label': 'Standard delivery', 'amount': 0, 'currency': 'USD'}]
    return rates


def checkout(request):
    """Step 1: contact + shipping address."""
    no_shipping = not _cart_requires_shipping(request)

    if request.method == 'GET':
        ctx = _checkout_base_context(request)
        ctx['no_shipping_required'] = no_shipping
        try:
            if not request.session.get('checkout_started'):
                from core.hooks import hook_registry, MorpheusEvents

                cart = ctx.get('cart')
                if cart is not None:
                    hook_registry.fire(
                        MorpheusEvents.BEGIN_CHECKOUT,
                        cart=cart,
                        customer=request.user if request.user.is_authenticated else None,
                        request=request,
                    )
                request.session['checkout_started'] = True
        except Exception:  # noqa: BLE001
            pass
        return render(request, 'storefront/checkout.html', ctx)
    fields = (
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
    addr = {f: (request.POST.get(f) or '').strip() for f in fields}
    _stamp_checkout_email(request, addr['email'])
    if no_shipping:
        if not addr['email']:
            ctx = _checkout_base_context(request)
            ctx['no_shipping_required'] = True
            ctx['error'] = 'Please enter the email where we should send your downloads.'
            ctx['form'] = addr
            return render(request, 'storefront/checkout.html', ctx)
        request.session['checkout_address'] = addr
        request.session['checkout_shipping_rate_id'] = 'no-shipping'
        request.session['checkout_shipping_rate_label'] = 'No shipping (digital)'
        return redirect('/checkout/review/')
    if not (addr['email'] and addr['address_line1'] and addr['city'] and addr['country']):
        ctx = _checkout_base_context(request)
        ctx['error'] = 'Please fill in email, address, city, and country.'
        ctx['form'] = addr
        return render(request, 'storefront/checkout.html', ctx)
    request.session['checkout_address'] = addr
    return redirect('/checkout/shipping/')


def checkout_apply_gift_card(request):
    """POST /checkout/gift-card/apply/ — applies the gift card and bounces back."""
    if request.method != 'POST':
        return redirect('/checkout/')
    code = (request.POST.get('code') or '').strip().upper()
    cart_id = request.session.get('cart_id') or ''
    if cart_id and code:
        mutation = """
        mutation Apply($input: ApplyGiftCardInput!) {
          applyGiftCard(input: $input) { errors { code message } }
        }
        """
        internal_graphql(
            mutation,
            variables={'input': {'cartId': cart_id, 'code': code}},
            request=request,
        )
    back = request.META.get('HTTP_REFERER', '/checkout/') or '/checkout/'
    return redirect(back)


def checkout_apply_coupon(request):
    """POST /checkout/coupon/apply/ — apply a promo code and bounce back.

    An invalid/expired code redirects back with ``?coupon=invalid`` so the
    form can show an inline error (the theme renders no messages framework).
    """
    if request.method != 'POST':
        return redirect('/checkout/quick/')
    code = (request.POST.get('code') or '').strip()
    cart_id = request.session.get('cart_id') or ''
    back = request.META.get('HTTP_REFERER', '/checkout/quick/') or '/checkout/quick/'
    back = back.split('?')[0]
    if cart_id and code:
        mutation = """
        mutation Apply($input: ApplyCouponInput!) {
          applyCoupon(input: $input) { errors { code message } }
        }
        """
        data = (
            internal_graphql(
                mutation,
                variables={'input': {'cartId': cart_id, 'code': code}},
                request=request,
            )
            or {}
        )
        errors = ((data.get('applyCoupon') or {}).get('errors')) or []
        if errors:
            return redirect(f'{back}?coupon=invalid')
    return redirect(back)


def checkout_remove_coupon(request):
    """POST /checkout/coupon/remove/ — clear the applied promo code."""
    if request.method != 'POST':
        return redirect('/checkout/quick/')
    cart_id = request.session.get('cart_id') or ''
    if cart_id:
        mutation = """
        mutation Remove($input: ApplyCouponInput!) {
          removeCoupon(input: $input) { errors { code message } }
        }
        """
        internal_graphql(
            mutation,
            variables={'input': {'cartId': cart_id, 'code': ''}},
            request=request,
        )
    back = request.META.get('HTTP_REFERER', '/checkout/quick/') or '/checkout/quick/'
    return redirect(back.split('?')[0])


def checkout_remove_gift_card(request):
    """POST /checkout/gift-card/remove/ — clears the applied card."""
    if request.method != 'POST':
        return redirect('/checkout/')
    cart_id = request.session.get('cart_id') or ''
    if cart_id:
        mutation = """
        mutation Remove($input: ApplyGiftCardInput!) {
          removeGiftCard(input: $input) { errors { code message } }
        }
        """
        internal_graphql(
            mutation,
            variables={'input': {'cartId': cart_id, 'code': ''}},
            request=request,
        )
    back = request.META.get('HTTP_REFERER', '/checkout/') or '/checkout/'
    return redirect(back)


def checkout_shipping(request):
    """Step 2: pick a shipping rate."""
    addr = request.session.get('checkout_address')
    if not addr:
        return redirect('/checkout/')
    if not _cart_requires_shipping(request):
        request.session.setdefault('checkout_shipping_rate_id', 'no-shipping')
        request.session.setdefault('checkout_shipping_rate_label', 'No shipping (digital)')
        return redirect('/checkout/review/')
    cart_data = internal_graphql(CART_QUERY, request=request) or {}
    cart = cart_data.get('cart') or {}

    rates = _available_shipping_rates(request, addr)

    if request.method == 'POST':
        rate_id = (request.POST.get('shipping_rate_id') or '').strip()
        if not rate_id and rates:
            rate_id = str(rates[0]['id'])
        request.session['checkout_shipping_rate_id'] = rate_id
        request.session['checkout_shipping_rate_label'] = next(
            (r['label'] for r in rates if str(r['id']) == rate_id),
            '',
        )
        return redirect('/checkout/review/')

    return render(
        request,
        'storefront/checkout_shipping.html',
        {
            'cart': cart,
            'address': addr,
            'rates': rates,
            'selected_rate_id': request.session.get('checkout_shipping_rate_id', ''),
        },
    )


def checkout_review(request):
    """Step 3: final review + place order. POST creates the Order +
    captures Stripe client_secret, then redirects to /checkout/payment/."""
    addr = request.session.get('checkout_address')
    if not addr:
        return redirect('/checkout/')
    cart_data = internal_graphql(CART_QUERY, request=request) or {}
    cart = cart_data.get('cart') or {}
    rate_label = request.session.get('checkout_shipping_rate_label', 'Standard')
    rate_id = request.session.get('checkout_shipping_rate_id', '')

    error = ''
    if request.method == 'POST':
        cart_id = (cart.get('id') or request.session.get('cart_id') or '').strip()
        waiver_err = waiver_gate(request)
        if not cart_id:
            error = 'Your cart has expired — add items again to continue.'
        elif waiver_err:
            error = waiver_err
        else:
            mutation = """
            mutation Complete($input: CompleteOrderInput!) {
              completeOrder(input: $input) { orderNumber paymentClientSecret errors { code message } }
            }
            """
            shipping_input = {
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
            data = (
                internal_graphql(
                    mutation,
                    variables={
                        'input': {
                            'cartId': cart_id,
                            'email': addr.get('email', ''),
                            'shippingAddress': shipping_input,
                            'shippingRateId': rate_id or None,
                        },
                    },
                    request=request,
                )
                or {}
            )
            payload = data.get('completeOrder') or {}
            errs = payload.get('errors') or []
            if errs:
                error = '; '.join(e.get('message', 'Order failed.') for e in errs)
            else:
                order_no = payload.get('orderNumber') or ''
                record_waiver(order_no)  # no-op when order_no is empty / non-digital
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
                    # Append the public token so a guest checkout (no
                    # account session) can still load the confirmation
                    # page. Owner-auth check in the view falls back to
                    # this token.
                    if order_no:
                        token = ''
                        try:
                            from plugins.installed.orders.models import Order as _Order

                            token = (
                                _Order.objects.filter(order_number=order_no)
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
                    return redirect('/account/orders/')
                return redirect('/checkout/payment/')

    _waiver = _withdrawal_waiver()
    return render(
        request,
        'storefront/checkout_review.html',
        {
            'cart': cart,
            'address': addr,
            'rate_label': rate_label,
            'error': error,
            'show_withdrawal_waiver': _waiver['enabled'] and _cart_has_digital(request),
            'withdrawal_waiver_text': _waiver['text'],
        },
    )


def checkout_payment(request):
    """Step 4: Stripe Payment Element."""
    from django.conf import settings as dj_settings

    order_no = request.session.get('checkout_order_number') or ''
    client_secret = request.session.get('checkout_client_secret') or ''
    if not (order_no and client_secret):
        return redirect('/checkout/')
    publishable = getattr(dj_settings, 'STRIPE_PUBLIC_KEY', '') or ''
    # Append public_token to the Stripe return URL so guest checkout
    # users keep access to the confirmation page (the view requires
    # either auth-owner or matching token).
    token = ''
    try:
        from plugins.installed.orders.models import Order as _Order

        token = (
            _Order.objects.filter(order_number=order_no)
            .values_list('public_token', flat=True)
            .first()
            or ''
        )
    except Exception:  # noqa: BLE001
        token = ''
    return_path = f'/order/confirmation/{order_no}/'
    if token:
        return_path = f'{return_path}?token={token}'
    return render(
        request,
        'storefront/checkout_payment.html',
        {
            'order_number': order_no,
            'client_secret': client_secret,
            'stripe_publishable_key': publishable,
            'return_url': request.build_absolute_uri(return_path),
        },
    )
