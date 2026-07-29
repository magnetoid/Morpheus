"""Auto-split from the legacy admin_dashboard/views.py monolith."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from morpheus.plugin.views import (
    HttpRequest,
    HttpResponse,
    get_object_or_404,
    messages,
    redirect,
    render,
    staff_member_required,
)
from plugins.installed.admin_dashboard.forms import (
    DraftOrderForm,
    FulfillmentForm,
    RefundForm,
)
from plugins.installed.admin_dashboard.views_split._shared import (
    _bulk_ids,
    ajax_or_redirect,
    logger,
    paginate_and_sort,
)

ORDER_STATUS_CHOICES = (
    ('', 'All'),
    ('pending', 'Pending'),
    ('confirmed', 'Confirmed'),
    ('processing', 'Processing'),
    ('fulfilled', 'Fulfilled'),
    ('shipped', 'Shipped'),
    ('delivered', 'Delivered'),
    ('cancelled', 'Cancelled'),
    ('refunded', 'Refunded'),
)


@staff_member_required
def orders_list(request: HttpRequest) -> HttpResponse:
    status_filter = request.GET.get('status', '')
    search = request.GET.get('q', '').strip()[:80]
    orders: list[Any] = []
    status_counts: dict[str, int] = {}
    paging_ctx: dict[str, Any] = {}
    try:
        from django.db.models import Count

        from plugins.installed.orders.models import Order

        unfiltered = Order.objects.all()
        if search:
            unfiltered = unfiltered.filter(order_number__icontains=search) | unfiltered.filter(
                email__icontains=search
            )
        status_counts = {
            row['status']: row['c'] for row in unfiltered.values('status').annotate(c=Count('id'))
        }
        qs = Order.objects.select_related('customer', 'channel')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(order_number__icontains=search) | qs.filter(email__icontains=search)
        page_obj, paging_ctx = paginate_and_sort(
            request,
            qs,
            default_sort='-placed_at',
            allowed_sorts=('placed_at', 'order_number', 'total', 'status', 'email'),
        )
        orders = list(page_obj.object_list)
        load_error = False
    except Exception:  # noqa: BLE001
        # Honest failure state — never render "No orders yet" over a DB error.
        logger.exception('orders_list: query failed')
        orders = []
        load_error = True
    # Drafts surface inside the Orders page rather than as a separate
    # sidebar entry — staff sees drafts and real orders side by side.
    draft_count = 0
    drafts_url = ''
    try:
        from plugins.installed.draft_orders.models import DraftOrder

        draft_count = DraftOrder.objects.exclude(status='converted').count()
        drafts_url = '/dashboard/draft-orders/'
    except Exception:  # noqa: BLE001, S110
        pass

    return render(
        request,
        'admin_dashboard/orders.html',
        {
            'orders': orders,
            'load_error': load_error,
            'status_filter': status_filter,
            'status_choices': ORDER_STATUS_CHOICES,
            'status_counts': status_counts,
            'search': search,
            'draft_count': draft_count,
            'drafts_url': drafts_url,
            'active_nav': 'orders',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Orders'},
            ],
            **paging_ctx,
        },
    )


@staff_member_required
def order_detail(request: HttpRequest, order_number: str) -> HttpResponse:
    order = None
    try:
        from plugins.installed.orders.models import Order

        order = (
            Order.objects.select_related('customer', 'channel')
            .prefetch_related('items', 'items__product', 'events', 'fulfillments')
            .get(order_number=order_number)
        )
    except Exception:  # noqa: BLE001
        order = None
    refunds: list[Any] = []
    refunded_total = Decimal('0')
    fulfillments: list[Any] = []
    if order is not None:
        try:
            refunds = list(order.refunds.all().order_by('-created_at'))
            refunded_total = sum(
                (Decimal(str(r.amount.amount)) for r in refunds),
                Decimal('0'),
            )
        except Exception:  # noqa: BLE001, S110
            pass
        try:  # noqa: SIM105
            fulfillments = list(
                order.fulfillments.all()
                .prefetch_related('items', 'items__order_item')
                .order_by('-created_at')
            )
        except Exception:  # noqa: BLE001, S110
            pass
    # Status stepper — happy-path stages a healthy order walks through.
    # `cancelled` / `refunded` aren't on this rail; they get a separate
    # red pill in the header.
    happy_path = ['pending', 'confirmed', 'processing', 'fulfilled', 'delivered']
    labels = {
        'pending': 'Pending',
        'confirmed': 'Confirmed',
        'processing': 'Processing',
        'fulfilled': 'Fulfilled',
        'delivered': 'Delivered',
    }
    cur_status = getattr(order, 'status', '') if order else ''
    cur_idx = happy_path.index(cur_status) if cur_status in happy_path else -1
    status_steps = [
        {
            'key': k,
            'label': labels[k],
            'done': cur_idx > i,
            'current': cur_idx == i,
        }
        for i, k in enumerate(happy_path)
    ]
    return render(
        request,
        'admin_dashboard/order_detail.html',
        {
            'order': order,
            'refunds': refunds,
            'refunded_total': refunded_total,
            'status_steps': status_steps,
            'fulfillments': fulfillments,
            'active_nav': 'orders',
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Orders', 'url': '/dashboard/orders/'},
                {'label': f'#{order.order_number}' if order else order_number},
            ],
        },
    )


# ── Products ──────────────────────────────────────────────────────────────────


@staff_member_required
def order_new(request: HttpRequest) -> HttpResponse:
    """Create a draft order from the dashboard.

    Real `orders.Order` rows are produced by the storefront checkout or by
    converting a draft — staff don't hand-craft FSM-managed orders.
    """
    customers: list[Any] = []
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        customers = list(User.objects.order_by('-date_joined')[:200])
    except Exception:  # noqa: BLE001, S110
        pass

    if request.method == 'POST':
        form = DraftOrderForm(request.POST)
        if form.is_valid():
            draft = form.save()
            messages.success(request, f'Draft order #{draft.number} created.')
            return redirect(f'/dashboard/draft-orders/{draft.number}/')
    else:
        form = DraftOrderForm()
    return render(
        request,
        'admin_dashboard/order_new.html',
        {
            'form': form,
            'customers': customers,
            'active_nav': 'orders',
        },
    )


def _mark_order_paid(order) -> bool:
    """Mark an order paid out-of-band (COD, bank transfer, manual) and fire
    ORDER_PAID exactly once. Every fulfillment side-effect — digital download
    tokens, loyalty points, CDP lifetime-value, ad-channel conversion pixels,
    the payment-confirmed email — hangs off ORDER_PAID, so simply flipping
    ``payment_status`` (as this used to) silently delivered nothing. Idempotent:
    a no-op (returns False) when the order is already paid, so a double click
    can't double-fire the event.
    """
    if order.payment_status == 'paid':
        return False
    from morpheus.core import MorpheusEvents, hook_registry

    order.payment_status = 'paid'
    order.save(update_fields=['payment_status', 'updated_at'])
    order.log_event('PAYMENT_MARKED_PAID', message='Marked paid via dashboard')
    hook_registry.fire(MorpheusEvents.ORDER_PAID, order=order)
    return True


@staff_member_required
def order_action(request: HttpRequest, order_number: str) -> HttpResponse:
    """POST-only side-effects on an existing order (cancel, mark paid, …)."""
    if request.method != 'POST':
        return redirect('admin_dashboard:order_detail', order_number=order_number)

    from plugins.installed.orders.models import Order

    order = get_object_or_404(Order, order_number=order_number)
    action = request.POST.get('action', '')

    try:
        if action == 'cancel':
            order.cancel(reason=request.POST.get('reason', '') or 'Cancelled from dashboard')
            order.save()
            messages.success(request, f'Order #{order.order_number} cancelled.')
        elif action == 'confirm':
            order.confirm()
            order.save()
            messages.success(request, f'Order #{order.order_number} confirmed.')
        elif action == 'process':
            order.process()
            order.save()
            messages.success(request, f'Order #{order.order_number} marked as processing.')
        elif action == 'fulfill':
            order.fulfill()
            order.save()
            messages.success(request, f'Order #{order.order_number} marked as fulfilled.')
        elif action == 'ship':
            tracking = (request.POST.get('tracking_number') or '').strip()[:200]
            order.ship(tracking_number=tracking)
            order.save()
            messages.success(request, f'Order #{order.order_number} marked as shipped.')
        elif action == 'deliver':
            order.deliver()
            order.save()
            messages.success(request, f'Order #{order.order_number} marked as delivered.')
        elif action == 'mark_paid':
            _mark_order_paid(order)
            messages.success(request, f'Order #{order.order_number} marked paid.')
        elif action == 'add_tracking':
            tracking = (request.POST.get('tracking_number') or '').strip()[:200]
            method = (request.POST.get('shipping_method') or '').strip()[:100]
            order.tracking_number = tracking
            if method:
                order.shipping_method = method
            order.save(update_fields=['tracking_number', 'shipping_method', 'updated_at'])
            order.log_event('TRACKING_UPDATED', message=tracking)
            messages.success(request, 'Tracking updated.')
        else:
            messages.error(request, f'Unknown action "{action}".')
    except Exception as e:  # noqa: BLE001 — FSM rejects illegal transitions
        logger.warning('order_action %s on %s failed: %s', action, order_number, e)
        messages.error(request, f'Action failed: {e}')

    return ajax_or_redirect(request, 'admin_dashboard:order_detail', order_number=order_number)


@staff_member_required
def order_fulfill(request: HttpRequest, order_number: str) -> HttpResponse:
    """Create a Fulfillment record for an order; optionally also flip the
    order's status to 'shipped' via the FSM."""
    from plugins.installed.orders.models import Order

    order = get_object_or_404(Order, order_number=order_number)
    if request.method == 'POST':
        form = FulfillmentForm(request.POST, order=order)
        if form.is_valid():
            f = form.save()
            if form.cleaned_data.get('mark_shipped') and order.status not in (
                'shipped',
                'delivered',
                'cancelled',
            ):
                try:
                    order.ship(tracking_number=f.tracking_number)
                    order.save()
                except Exception as e:  # noqa: BLE001 — FSM rejects illegal moves
                    logger.warning('order_fulfill: ship transition failed: %s', e)
            messages.success(request, f'Fulfillment created for order #{order.order_number}.')
            return redirect('admin_dashboard:order_detail', order_number=order.order_number)
    else:
        form = FulfillmentForm(order=order)
    return render(
        request,
        'admin_dashboard/order_fulfill.html',
        {
            'form': form,
            'order': order,
            'active_nav': 'orders',
        },
    )


@staff_member_required
def order_refund(request: HttpRequest, order_number: str) -> HttpResponse:
    from plugins.installed.orders.models import Order

    order = get_object_or_404(Order, order_number=order_number)
    if request.method == 'POST':
        form = RefundForm(request.POST, order=order)
        if form.is_valid():
            refund = form.save()
            messages.success(request, f'Refund of {refund.amount} recorded.')
            return redirect('admin_dashboard:order_detail', order_number=order.order_number)
    else:
        form = RefundForm(order=order)
    return render(
        request,
        'admin_dashboard/order_refund.html',
        {
            'form': form,
            'order': order,
            'active_nav': 'orders',
        },
    )


# ── Product variants ──────────────────────────────────────────────────────────


@staff_member_required
def orders_bulk(request: HttpRequest) -> HttpResponse:
    """Bulk action endpoint for the orders list page.

    Supported actions: ``mark_paid`` (flip payment_status to paid),
    ``cancel`` (transition to cancelled, fires the cancel hook),
    ``export`` (redirect to the importers/csv export with a pre-filtered
    set — placeholder; falls back to the full export).
    """
    if request.method != 'POST':
        return redirect('admin_dashboard:orders')
    from plugins.installed.orders.models import Order

    action = (request.POST.get('action') or '').strip()
    ids = _bulk_ids(request)
    if not ids:
        messages.warning(request, 'No orders selected.')
        return redirect('admin_dashboard:orders')

    qs = Order.objects.filter(pk__in=ids)
    count = qs.count()
    if count == 0:
        messages.warning(request, 'No matching orders found.')
        return redirect('admin_dashboard:orders')

    if action == 'mark_paid':
        # Per-order (not qs.update) so ORDER_PAID fires for each — a bulk
        # payment_status update skipped all fulfillment side-effects.
        paid = 0
        for o in qs:
            try:
                if _mark_order_paid(o):
                    paid += 1
            except Exception:  # noqa: BLE001, S112 — one bad order must not abort the batch
                continue
        messages.success(request, f'Marked {paid} order(s) as paid.')
    elif action == 'cancel':
        # Go through the FSM (order.cancel) — direct `o.status = 'cancelled'` on
        # the protected FSMField raises and was silently swallowed, so nothing
        # cancelled and no ORDER_CANCELLED (stock release / email) fired.
        ok = 0
        for o in qs:
            try:
                o.cancel(reason='Bulk cancel from dashboard')
                o.save()
                ok += 1
            except Exception:  # noqa: BLE001, S112 — skip orders in a non-cancellable state
                continue
        messages.success(request, f'Cancelled {ok} order(s).')
    elif action == 'export':
        return redirect('/dashboard/apps/importers/csv/')
    else:
        messages.warning(request, f'Unknown action: {action!r}.')
    return redirect('admin_dashboard:orders')
