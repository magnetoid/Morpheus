"""Customer account pages: profile, orders, addresses, returns,
credits, downloads, order confirmation. All guarded by _login_required.
"""
from __future__ import annotations

from morpheus.views import render


def _login_required(request, target):
    if not request.user.is_authenticated:
        from django.shortcuts import redirect as _redirect
        return _redirect(f'/auth/login/?next={target}')
    return None


def _account_summary(user) -> dict:
    """Cheap counts + balances for the account home dashboard.
    Fail-soft per plugin — a missing plugin shouldn't break the page."""
    s: dict = {
        'orders_count': 0,
        'pending_returns': 0,
        'store_credit_balance': None,
        'gift_card_count': 0,
        'gift_card_total': None,
        'download_count': 0,
        'loyalty_points': 0,
    }
    try:
        from plugins.installed.loyalty_points.services import get_balance as _lb
        s['loyalty_points'] = _lb(user)
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.orders.models import Order
        s['orders_count'] = Order.objects.filter(customer=user).count()
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.orders.refunds import ReturnRequest
        s['pending_returns'] = ReturnRequest.objects.filter(
            order__customer=user, state__in=('requested', 'approved', 'received'),
        ).count()
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.orders import store_credit as _sc
        s['store_credit_balance'] = _sc.balance(user)
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.gift_cards.models import GiftCard
        from decimal import Decimal
        cards = GiftCard.objects.filter(
            issued_to_customer=user, state='active',
        )
        s['gift_card_count'] = cards.count()
        if cards.exists():
            total = sum(
                (Decimal(str(c.balance.amount)) for c in cards),
                Decimal('0'),
            )
            currency = str(cards.first().balance.currency)
            from djmoney.money import Money
            s['gift_card_total'] = Money(total, currency)
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.digital_products.models import DownloadToken
        from django.utils import timezone
        s['download_count'] = DownloadToken.objects.filter(
            order__customer=user,
            expires_at__gt=timezone.now(),
            revoked_at__isnull=True,
        ).count()
    except Exception:  # noqa: BLE001
        pass
    return s


def account_home(request):
    if not request.user.is_authenticated:
        from morpheus.views import redirect
        return redirect('/auth/login/?next=/account/')
    summary = _account_summary(request.user)
    return render(request, 'storefront/account_home.html', {
        'user': request.user,
        'summary': summary,
    })


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
        orders = list(
            Order.objects.filter(customer=request.user)
            .order_by('-created_at')[:50]
        )
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
        order_number=order_number, customer=request.user,
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
        rrs = list(ReturnRequest.objects.filter(
            order__customer=request.user,
        ).order_by('-created_at'))
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
        pk=rma_id, order__customer=request.user,
    )

    happy_path = ['requested', 'approved', 'received', 'refunded']
    labels = {
        'requested': 'Requested', 'approved': 'Approved',
        'received': 'Received', 'refunded': 'Refunded',
    }
    cur_idx = happy_path.index(rr.state) if rr.state in happy_path else -1
    status_steps = [
        {'key': k, 'label': labels[k],
         'done': cur_idx > i, 'current': cur_idx == i}
        for i, k in enumerate(happy_path)
    ]

    from plugins.installed.orders.models import OrderItem
    items_by_id = {str(o.pk): o for o in OrderItem.objects.filter(order=rr.order)}
    line_items = []
    for entry in (rr.items or []):
        oi = items_by_id.get(str(entry.get('order_item_id', '')))
        if oi is None:
            continue
        line_items.append({
            'name': oi.product_name, 'sku': oi.sku,
            'quantity': entry.get('quantity', 0),
            'unit_price': oi.unit_price,
        })

    return render(request, 'storefront/account_return_status.html', {
        'rma': rr, 'order': rr.order,
        'status_steps': status_steps,
        'line_items': line_items,
        'is_terminal': rr.state in ('refunded', 'cancelled', 'rejected'),
    })


def account_order_return(request, order_number):
    redirect_resp = _login_required(request, f'/account/orders/{order_number}/return/')
    if redirect_resp is not None:
        return redirect_resp
    from django.shortcuts import get_object_or_404, redirect as _redirect
    from plugins.installed.orders.models import Order
    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        order_number=order_number, customer=request.user,
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
                order=order, items=items,
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
            StoreCreditTxn.objects.filter(customer=request.user)
            .order_by('-created_at')[:30]
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.gift_cards.models import GiftCard
        cards = list(
            GiftCard.objects
            .filter(issued_to_customer=request.user, state='active')
            .order_by('-created_at')
        )
    except Exception:  # noqa: BLE001
        pass
    return render(request, 'storefront/account_credits.html', {
        'store_credit': store_credit,
        'txns': txns,
        'cards': cards,
    })


def account_downloads(request):
    """Active digital download links — token-protected, time-bound."""
    if not request.user.is_authenticated:
        from morpheus.views import redirect
        return redirect('/auth/login/?next=/account/downloads/')
    tokens: list = []
    try:
        from plugins.installed.digital_products.models import DownloadToken
        from django.utils import timezone
        tokens = list(
            DownloadToken.objects
            .filter(order__customer=request.user, revoked_at__isnull=True)
            .select_related('product', 'order')
            .order_by('-created_at')[:50]
        )
        now = timezone.now()
        for t in tokens:
            t.is_expired = bool(t.expires_at and t.expires_at <= now)
            t.is_exhausted = t.downloads_used >= t.max_downloads
    except Exception:  # noqa: BLE001
        pass
    return render(request, 'storefront/account_downloads.html', {
        'tokens': tokens,
    })


def order_confirmation(request, order_number):
    """Public order confirmation — accessible by order_number alone.
    Stripe redirects here after a successful confirmPayment."""
    from morpheus.views import get_object_or_404
    from plugins.installed.orders.models import Order
    order = get_object_or_404(
        Order.objects.prefetch_related('items'), order_number=order_number,
    )
    for k in ('checkout_order_number', 'checkout_client_secret'):
        request.session.pop(k, None)
    redirect_status = (request.GET.get('redirect_status') or '').lower()
    return render(request, 'storefront/order_confirmation.html', {
        'order': order,
        'payment_status': redirect_status,
    })
