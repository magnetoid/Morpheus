"""``/pay/<token>/``: the customer pays an order that is already placed (A8).

A GET only shows the order and the ways to pay: email link scanners open every
link, and a payment started on a GET would leave a Stripe intent per scan. A
POST starts it through the checkout's own routing, so the card goes through the
checkout's payment step, PayPal through its approval page, and an offline method
to the order confirmation.
"""

from __future__ import annotations

from django.http import Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from morpheus.app.views import redirect, render

#: ``secrets.token_urlsafe(32)``, the length of every order's public token.
_TOKEN_LENGTH = 43


@never_cache
@require_http_methods(['GET', 'POST'])
def pay_order(request, token: str):
    from plugins.installed.orders.models import Order  # noqa: PLC0415
    from plugins.installed.payments import pay_link  # noqa: PLC0415
    from plugins.installed.payments.services import routing  # noqa: PLC0415

    token = (token or '').strip()
    if len(token) != _TOKEN_LENGTH:
        raise Http404('Order not found')
    # A 256-bit random token: the lookup itself is the access check.
    order = Order.objects.prefetch_related('items').filter(public_token=token).first()
    if order is None:
        raise Http404('Order not found')

    current = pay_link.state(order)
    methods = []
    if current == 'payable':
        methods = routing.picker_gateways(user=order.customer, ships=routing.order_ships(order))
    selected = (request.POST.get('payment_method') or '').strip()
    error = ''
    if request.method == 'POST' and current == 'payable' and methods:
        slugs = [m['slug'] for m in methods]
        if not selected and len(slugs) == 1:
            selected = slugs[0]
        if selected not in slugs:
            error = 'Choose a way to pay.'
        else:
            result = routing.create_payment_intent_for(order, selected)
            if result.get('success'):
                return _continue(request, order, result)
            error = result.get('error') or 'The payment could not be started. Please try again.'
    if not selected:
        selected = next((m['slug'] for m in methods if m['is_default']), '')

    return render(
        request,
        'payments/pay.html',
        {
            'order': order,
            'pay_state': current,
            'payment_methods': methods,
            'selected_payment_method': selected,
            'error': error,
            'seo_title': f'Pay for order #{order.order_number}',
        },
    )


def _continue(request, order, result: dict):
    """Where the started payment goes next: the card form, PayPal, or the receipt."""
    client_secret = result.get('client_secret') or ''
    if client_secret:
        # The checkout's payment step reads these two (storefront checkout_payment).
        request.session['checkout_order_number'] = order.order_number
        request.session['checkout_client_secret'] = client_secret
        return redirect('/checkout/payment/')
    approval_url = result.get('approval_url') or ''
    if approval_url:
        return redirect(approval_url)
    return redirect(f'/order/confirmation/{order.order_number}/?token={order.public_token}')
