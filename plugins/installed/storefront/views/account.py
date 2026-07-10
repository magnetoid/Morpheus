"""Customer account pages: profile, orders, addresses, returns,
credits, downloads, order confirmation. All guarded by _login_required.
"""

# ruff: noqa: PLC0415, I001
# Inline imports are intentional throughout this module — plugin models
# are imported lazily so a disabled plugin drops out without breaking the
# account page (each block is wrapped in try/except).
from __future__ import annotations

import logging

from morpheus.views import render

logger = logging.getLogger('morpheus.storefront')


def _login_required(request, target):
    if not request.user.is_authenticated:
        from django.shortcuts import redirect as _redirect

        return _redirect(f'/auth/login/?next={target}')
    return None


def _gdpr_required() -> None:
    """404 the self-service GDPR pages when the store has turned GDPR features
    off (Settings → General → GDPR/ePrivacy). Default ON, so no change unless
    a merchant outside GDPR jurisdiction opts out."""
    from core.models import StoreSettings

    if not StoreSettings.get('gdpr_enabled', True):
        from django.http import Http404

        raise Http404('GDPR features are disabled for this store.')


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
        from core.hooks import MorpheusEvents, hook_registry

        s = hook_registry.filter(MorpheusEvents.ACCOUNT_SUMMARY_FIELDS, value=s, user=user)
    except Exception as e:  # noqa: BLE001
        logger.warning('account_summary.filter failed: %s', e, exc_info=True)
    return s


def account_home(request):
    if not request.user.is_authenticated:
        from morpheus.views import redirect

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
            user.email = new_email[:254]
        user.save(update_fields=['first_name', 'last_name', 'email'])
        from django.shortcuts import redirect as _redirect

        return _redirect('storefront:account_profile')
    return render(request, 'storefront/account_profile.html', {'user': user})


def account_orders(request):
    if not request.user.is_authenticated:
        from morpheus.views import redirect

        return redirect('/auth/login/?next=/account/orders/')
    try:
        from plugins.installed.orders.models import Order

        orders = list(Order.objects.filter(customer=request.user).order_by('-created_at')[:50])
    except Exception:  # noqa: BLE001
        orders = []
    return render(request, 'storefront/account_orders.html', {'orders': orders})


def account_order_detail(request, order_number):
    if not request.user.is_authenticated:
        from morpheus.views import redirect

        return redirect(f'/auth/login/?next=/account/orders/{order_number}/')
    from morpheus.views import get_object_or_404
    from plugins.installed.orders.models import Order

    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        order_number=order_number,
        customer=request.user,
    )
    return render(request, 'storefront/account_order_detail.html', {'order': order})


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
        from morpheus.views import get_object_or_404

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


def account_returns(request):
    redirect_resp = _login_required(request, '/account/returns/')
    if redirect_resp is not None:
        return redirect_resp
    try:
        from plugins.installed.orders.refunds import ReturnRequest

        rrs = list(
            ReturnRequest.objects.filter(
                order__customer=request.user,
            ).order_by('-created_at')
        )
    except Exception:  # noqa: BLE001
        rrs = []
    return render(request, 'storefront/account_returns.html', {'returns': rrs})


def account_return_status(request, rma_id):
    """Per-RMA status page — four-step pill row so the customer can
    track their return without emailing support."""
    redirect_resp = _login_required(request, f'/account/returns/{rma_id}/')
    if redirect_resp is not None:
        return redirect_resp
    from django.shortcuts import get_object_or_404
    from plugins.installed.orders.refunds import ReturnRequest

    rr = get_object_or_404(
        ReturnRequest.objects.select_related('order'),
        pk=rma_id,
        order__customer=request.user,
    )

    happy_path = ['requested', 'approved', 'received', 'refunded']
    labels = {
        'requested': 'Requested',
        'approved': 'Approved',
        'received': 'Received',
        'refunded': 'Refunded',
    }
    cur_idx = happy_path.index(rr.state) if rr.state in happy_path else -1
    status_steps = [
        {'key': k, 'label': labels[k], 'done': cur_idx > i, 'current': cur_idx == i}
        for i, k in enumerate(happy_path)
    ]

    from plugins.installed.orders.models import OrderItem

    items_by_id = {str(o.pk): o for o in OrderItem.objects.filter(order=rr.order)}
    line_items = []
    for entry in rr.items or []:
        oi = items_by_id.get(str(entry.get('order_item_id', '')))
        if oi is None:
            continue
        line_items.append(
            {
                'name': oi.product_name,
                'sku': oi.sku,
                'quantity': entry.get('quantity', 0),
                'unit_price': oi.unit_price,
            }
        )

    return render(
        request,
        'storefront/account_return_status.html',
        {
            'rma': rr,
            'order': rr.order,
            'status_steps': status_steps,
            'line_items': line_items,
            'is_terminal': rr.state in ('refunded', 'cancelled', 'rejected'),
        },
    )


def account_order_return(request, order_number):
    redirect_resp = _login_required(request, f'/account/orders/{order_number}/return/')
    if redirect_resp is not None:
        return redirect_resp
    from django.shortcuts import get_object_or_404, redirect as _redirect
    from plugins.installed.orders.models import Order

    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        order_number=order_number,
        customer=request.user,
    )
    if request.method == 'POST':
        from plugins.installed.orders.refunds import ReturnService

        items = []
        for item in order.items.all():
            qty = int(request.POST.get(f'qty_{item.id}', 0) or 0)
            if qty > 0:
                items.append({'order_item_id': str(item.id), 'quantity': min(qty, item.quantity)})
        if items:
            rr = ReturnService.create_request(
                order=order,
                items=items,
                reason=request.POST.get('reason', 'other'),
                customer_note=(request.POST.get('note', '') or '')[:2000],
                requested_by=request.user,
            )
            return _redirect('storefront:account_return_status', rma_id=rr.id)
        return _redirect('storefront:account_returns')
    return render(request, 'storefront/account_order_return.html', {'order': order})


def account_credits(request):
    """Combined view: store-credit balance + ledger + active gift cards."""
    if not request.user.is_authenticated:
        from morpheus.views import redirect

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
        from plugins.registry import plugin_registry

        if plugin_registry.is_active('gift_cards'):
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


def account_data_export(request):
    """GDPR Art. 15 — right to access.

    GET renders a confirmation page describing what's in the export.
    POST builds a ZIP of JSON files (one per data category) and streams
    it back as an attachment. Plugin-specific categories are imported
    lazily inside ``gather_customer_data`` so disabled plugins drop out
    of the export silently.
    """
    _gdpr_required()
    redirect_resp = _login_required(request, '/account/data-export/')
    if redirect_resp is not None:
        return redirect_resp
    if request.method == 'POST':
        import io  # noqa: PLC0415
        import json  # noqa: PLC0415
        import zipfile  # noqa: PLC0415
        from datetime import date  # noqa: PLC0415

        from django.http import HttpResponse  # noqa: PLC0415

        from plugins.installed.customers.services import gather_customer_data  # noqa: PLC0415

        data_by_filename = gather_customer_data(request.user)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename, payload in data_by_filename.items():
                zf.writestr(filename, json.dumps(payload, indent=2, default=str))
        resp = HttpResponse(buf.getvalue(), content_type='application/zip')
        fname = f'dotbooks-data-{request.user.pk}-{date.today().isoformat()}.zip'
        resp['Content-Disposition'] = f'attachment; filename="{fname}"'
        return resp
    return render(request, 'storefront/account_data_export.html', {'user': request.user})


def account_delete(request):
    """GDPR Art. 17 — right to be forgotten.

    GET renders a destructive-action confirmation page. POST requires the
    user to type their own email back, then anonymises the account, logs
    them out, and redirects to /.
    """
    _gdpr_required()
    redirect_resp = _login_required(request, '/account/delete/')
    if redirect_resp is not None:
        return redirect_resp
    error = None
    if request.method == 'POST':
        from django.contrib import messages  # noqa: PLC0415
        from django.contrib.auth import logout  # noqa: PLC0415
        from django.db import transaction  # noqa: PLC0415
        from django.shortcuts import redirect as _redirect  # noqa: PLC0415

        from plugins.installed.customers.services import anonymise_customer  # noqa: PLC0415

        typed = (request.POST.get('confirm_email') or '').strip().lower()
        if typed != (request.user.email or '').lower():
            error = "That email doesn't match the one on your account."
        else:
            customer = request.user
            with transaction.atomic():
                anonymise_customer(customer)
            logout(request)
            messages.success(
                request,
                'Your account is gone. Your reviews and orders have been '
                "anonymised. We're sorry to see you go.",
            )
            return _redirect('/')
    return render(
        request,
        'storefront/account_delete.html',
        {'user': request.user, 'error': error},
    )


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

    from django.conf import settings as dj_settings
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
            'stripe_publishable_key': getattr(dj_settings, 'STRIPE_PUBLIC_KEY', '') or '',
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
    from morpheus.views import get_object_or_404

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
        },
    )
