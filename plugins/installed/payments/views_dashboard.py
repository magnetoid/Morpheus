"""The order page's Charge button (the Payment panel)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.authz import require_capability


@staff_member_required
@require_capability('orders.write')
@require_POST
def capture(request, order_number: str):
    """Charge the order's held card payment now."""
    from plugins.installed.orders.models import Order  # noqa: PLC0415
    from plugins.installed.payments.services.capture import capture_order  # noqa: PLC0415

    order = get_object_or_404(Order, order_number=order_number)
    result = capture_order(order)
    if result.get('success'):
        messages.success(request, f'Order #{order.order_number} was charged.')
    else:
        messages.error(request, result.get('error') or 'The payment could not be charged.')
    return redirect(reverse('admin_dashboard:order_detail', args=[order.order_number]))
