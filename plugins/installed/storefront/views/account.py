"""Customer account pages: profile, orders, addresses, returns,
credits, downloads, order confirmation. All guarded by _login_required.
"""

# ruff: noqa: PLC0415, I001
# Inline imports are intentional throughout this module — plugin models
# are imported lazily so a disabled plugin drops out without breaking the
# account page (each block is wrapped in try/except).
from __future__ import annotations

import contextlib
import logging

from morpheus.app.views import render
from core.security_headers import payment_page

logger = logging.getLogger('morpheus.storefront')


def _login_required(request, target):
    if not request.user.is_authenticated:
        from django.shortcuts import redirect as _redirect

        return _redirect(f'/auth/login/?next={target}')
    return None


def _account_summary(user) -> dict:
    """Counts + balances for the account home dashboard.

    Assembled entirely through the ``ACCOUNT_SUMMARY_FIELDS`` filter (see
    core/hooks.py): each enabled plugin folds its own field(s) into the
    dict — orders (order count / open returns / store credit), loyalty,
    gift_cards, digital_products all subscribe — so a disabled plugin's
    tile vanishes automatically and this view imports no plugin models.
    Fail-soft: the hook bus isolates a broken subscriber.
    """
    s: dict = {}
    try:
        from morpheus.core import MorpheusEvents, hook_registry

        s = hook_registry.filter(MorpheusEvents.ACCOUNT_SUMMARY_FIELDS, value=s, user=user)
    except Exception as e:  # noqa: BLE001
        logger.warning('account_summary.filter failed: %s', e, exc_info=True)
    return s


def account_home(request):
    if not request.user.is_authenticated:
        from morpheus.app.views import redirect

        return redirect('/auth/login/?next=/account/')
    summary = _account_summary(request.user)
    return render(
        request,
        'storefront/account_home.html',
        {
            'user': request.user,
            'summary': summary,
        },
    )


def account_profile(request):
    redirect_resp = _login_required(request, '/account/profile/')
    if redirect_resp is not None:
        return redirect_resp
    user = request.user
    if request.method == 'POST':
        for field in ('first_name', 'last_name'):
            val = (request.POST.get(field) or '').strip()
            if val:
                setattr(user, field, val[:120])
        new_email = (request.POST.get('email') or '').strip().lower()
        if new_email and new_email != user.email:
            # Customer.email is unique: saving another account's address
            # raised IntegrityError (a 500) and lost the name change with it.
            from django.contrib.auth import get_user_model

            taken = (
                get_user_model()
                .objects.filter(email__iexact=new_email)
                .exclude(pk=user.pk)
                .exists()
            )
            if taken:
                from django.contrib import messages

                messages.error(request, 'That email address is already used by another account.')
            else:
                user.email = new_email[:254]
        user.save(update_fields=['first_name', 'last_name', 'email'])
        from django.shortcuts import redirect as _redirect

        return _redirect('storefront:account_profile')
    return render(request, 'storefront/account_profile.html', {'user': user})


def account_orders(request):
    if not request.user.is_authenticated:
        from morpheus.app.views import redirect

        return redirect('/auth/login/?next=/account/orders/')
    try:
        from plugins.installed.orders.models import Order

        # An order is dated by placed_at. Sorting on a created_at it never had raised a
        # FieldError this block swallowed, so every customer's history was empty
        # until v0.148.0; a failure here is now logged as the error it is.
        orders = list(Order.objects.filter(customer=request.user).order_by('-placed_at')[:50])
    except Exception:  # noqa: BLE001 — the account page still renders
        logger.exception('account orders failed')
        orders = []
    return render(request, 'storefront/account_orders.html', {'orders': orders})


def account_order_detail(request, order_number):
    if not request.user.is_authenticated:
        from morpheus.app.views import redirect

        return redirect(f'/auth/login/?next=/account/orders/{order_number}/')
    from morpheus.app.views import get_object_or_404
    from plugins.installed.orders.models import Order

    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        order_number=order_number,
        customer=request.user,
    )
    from plugins.installed.orders.cancellation import customer_can_cancel

    return render(
        request,
        'storefront/account_order_detail.html',
        {'order': order, 'can_cancel': customer_can_cancel(order)},
    )


def account_order_cancel(request, order_number):
    """Customer-initiated cancellation before the order is packed (EU right of
    withdrawal).

    Goes through orders' one cancel rule (``orders.cancellation``): a paid order
    is paid back in full unless the store set ``customer_cancel_paid`` to
    'contact', and a refund that fails leaves the order cancelled with the
    refund to settle. The refund confirmation reaches the customer through the
    standard PAYMENT_REFUNDED email, so this view redirects back to the order.
    """
    redirect_resp = _login_required(request, f'/account/orders/{order_number}/')
    if redirect_resp is not None:
        return redirect_resp
    from django.shortcuts import get_object_or_404, redirect as _redirect
    from plugins.installed.orders.cancellation import CancelRefused, cancel_with_refund
    from plugins.installed.orders.models import Order

    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    detail = _redirect('storefront:account_order_detail', order_number=order_number)
    if request.method != 'POST':
        return detail
    # The button is rendered only while the order can be cancelled, so a refusal
    # is a stale form or a hand-crafted POST: nothing to do.
    with contextlib.suppress(CancelRefused):
        cancel_with_refund(
            order,
            reason='Customer withdrawal (pre-dispatch)',
            actor=request.user,
            by_customer=True,
        )
    return detail


def account_addresses(request):
    redirect_resp = _login_required(request, '/account/addresses/')
    if redirect_resp is not None:
        return redirect_resp
    addresses = list(request.user.addresses.all().order_by('-is_default', '-created_at'))
    return render(request, 'storefront/account_addresses.html', {'addresses': addresses})


def account_address_form(request, address_id=None):
    redirect_resp = _login_required(request, '/account/addresses/')
    if redirect_resp is not None:
        return redirect_resp
    from plugins.installed.customers.models import Address

    address = None
    if address_id:
        from morpheus.app.views import get_object_or_404

        address = get_object_or_404(Address, id=address_id, customer=request.user)
    if request.method == 'POST':
        from django.shortcuts import redirect as _redirect

        data = {
            'first_name': (request.POST.get('first_name') or '')[:100],
            'last_name': (request.POST.get('last_name') or '')[:100],
            'company': (request.POST.get('company') or '')[:200],
            'address_line1': (request.POST.get('address_line1') or '')[:255],
            'address_line2': (request.POST.get('address_line2') or '')[:255],
            'city': (request.POST.get('city') or '')[:100],
            'state': (request.POST.get('state') or '')[:100],
            'postal_code': (request.POST.get('postal_code') or '')[:20],
            'country': (request.POST.get('country') or 'US')[:2].upper(),
            'phone': (request.POST.get('phone') or '')[:30],
            'is_default': bool(request.POST.get('is_default')),
            'address_type': request.POST.get('address_type', 'shipping'),
        }
        if address is not None:
            for k, v in data.items():
                setattr(address, k, v)
            address.save()
        else:
            Address.objects.create(customer=request.user, **data)
        return _redirect('storefront:account_addresses')
    return render(request, 'storefront/account_address_form.html', {'address': address})


def account_address_delete(request, address_id):
    redirect_resp = _login_required(request, '/account/addresses/')
    if redirect_resp is not None:
        return redirect_resp
    from django.shortcuts import get_object_or_404, redirect as _redirect
    from plugins.installed.customers.models import Address

    address = get_object_or_404(Address, id=address_id, customer=request.user)
    if request.method == 'POST':
        address.delete()
    return _redirect('storefront:account_addresses')


def account_credits(request):
    """Combined view: store-credit balance + ledger + active gift cards."""
    if not request.user.is_authenticated:
        from morpheus.app.views import redirect

        return redirect('/auth/login/?next=/account/credits/')
    store_credit = None
    txns: list = []
    cards: list = []
    try:
        from plugins.installed.orders import store_credit as _sc
        from plugins.installed.orders.models import StoreCreditTxn

        store_credit = _sc.balance(request.user)
        txns = list(
            StoreCreditTxn.objects.filter(customer=request.user).order_by('-created_at')[:30]
        )
    except Exception as e:  # noqa: BLE001
        logger.warning('account_credits.store_credit failed: %s', e, exc_info=True)
    try:
        # Gift cards are an optional plugin: only query them while it's enabled,
        # so disabling gift_cards removes the section here (ADR 0013). Store
        # credit (orders) stays — it's foundational, so this page itself remains.
        from plugins.registry import app_registry

        if app_registry.is_active('gift_cards'):
            from plugins.installed.gift_cards.models import GiftCard

            cards = list(
                GiftCard.objects.filter(issued_to_customer=request.user, state='active').order_by(
                    '-created_at'
                )
            )
    except Exception as e:  # noqa: BLE001
        logger.warning('account_credits.gift_cards failed: %s', e, exc_info=True)
    return render(
        request,
        'storefront/account_credits.html',
        {
            'store_credit': store_credit,
            'txns': txns,
            'cards': cards,
        },
    )


# GDPR self-service data-rights views (Art. 15 export / Art. 17 erasure) moved
# to the `gdpr` plugin (plugins/installed/gdpr/) — routed at /account/privacy/,
# /account/data-export/, /account/delete/. These were previously dead code here
# (never URL-routed); the gdpr plugin now owns and routes them.


@payment_page
def account_payment_methods(request):
    """Saved card vault — list + add (SetupIntent) + delete.

    GET renders the cards from Stripe plus a SetupIntent client_secret
    the page mounts in a Stripe Payment Element for the add-card flow.
    POST with `delete_id` detaches a single card. We never store the
    pm_… on our side; Stripe is the source of truth.
    """
    redirect_resp = _login_required(request, '/account/payment-methods/')
    if redirect_resp is not None:
        return redirect_resp

    from django.shortcuts import redirect as _redirect

    from plugins.installed.payments.services import stripe as stripe_svc

    error = ''
    notice = ''

    if request.method == 'POST':
        pm_id = (request.POST.get('delete_id') or '').strip()
        if pm_id:
            try:
                ok = stripe_svc.detach_payment_method(pm_id, request.user)
                notice = 'Card removed.' if ok else "We couldn't find that card on your account."
            except Exception:  # noqa: BLE001
                error = "We couldn't remove that card. Try again in a moment."
        return _redirect('storefront:account_payment_methods')

    cards: list = []
    client_secret = ''
    try:
        cards = stripe_svc.list_payment_methods(request.user)
    except Exception:  # noqa: BLE001
        error = "We couldn't load your saved cards just now. Please refresh."
    try:
        client_secret = stripe_svc.create_setup_intent(request.user)
    except Exception:  # noqa: BLE001
        # Setup intent is only needed for the add-card mount; if it
        # fails the list still renders, the add form just won't.
        client_secret = ''

    return render(
        request,
        'storefront/account_payment_methods.html',
        {
            'cards': cards,
            'setup_client_secret': client_secret,
            'stripe_publishable_key': stripe_svc.PaymentService.get_stripe_public_key(),
            'return_url': request.build_absolute_uri('/account/payment-methods/'),
            'error': error,
            'notice': notice,
        },
    )


def order_confirmation(request, order_number):
    """Order confirmation — auth'd customer OR ?token=<public_token>.

    Stripe redirects here after a successful confirmPayment. To avoid
    leaking order existence we 404 (not 403) on any auth failure.
    """
    from django.http import Http404
    from morpheus.app.views import get_object_or_404

    from plugins.installed.orders.models import Order

    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        order_number=order_number,
    )
    # Access check: either the logged-in customer owns the order, or a
    # matching public_token is supplied. constant-time-compare the token
    # to avoid timing attacks.
    import hmac

    supplied = (request.GET.get('token') or '').strip()
    is_owner = (
        request.user.is_authenticated
        and order.customer_id is not None
        and order.customer_id == request.user.pk
    )
    token_ok = (
        bool(supplied)
        and bool(order.public_token)
        and hmac.compare_digest(
            supplied,
            order.public_token,
        )
    )
    if not (is_owner or token_ok):
        # Don't leak that the order exists — same response as a wrong
        # order_number.
        raise Http404('Order not found')

    for k in ('checkout_order_number', 'checkout_client_secret'):
        request.session.pop(k, None)
    redirect_status = (request.GET.get('redirect_status') or '').lower()
    return render(
        request,
        'storefront/order_confirmation.html',
        {
            'order': order,
            'payment_status': redirect_status,
            # Downloads are taken from the email or the Library, never from here.
            'delivery_surface': 'receipt',
        },
    )
