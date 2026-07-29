"""Auto-split from the legacy admin_dashboard/views.py monolith."""

from __future__ import annotations

from morpheus.plugin.views import (
    HttpRequest,
    HttpResponse,
    get_object_or_404,
    render,
    staff_member_required,
)


@staff_member_required
def returns_list(request: HttpRequest) -> HttpResponse:
    from plugins.installed.orders.refunds import ReturnRequest

    state = (request.GET.get('state') or '').strip()
    qs = ReturnRequest.objects.select_related('order', 'order__customer').order_by('-created_at')
    if state:
        qs = qs.filter(state=state)
    rows = list(qs[:200])
    counts = {
        s[0]: ReturnRequest.objects.filter(state=s[0]).count() for s in ReturnRequest.STATE_CHOICES
    }
    return render(
        request,
        'admin_dashboard/returns_list.html',
        {
            'rows': rows,
            'counts': counts,
            'state': state,
            'state_choices': ReturnRequest.STATE_CHOICES,
            'active_nav': 'orders',
        },
    )


@staff_member_required
def return_detail(request: HttpRequest, rma_id) -> HttpResponse:
    from morpheus.plugin.views import HttpResponseRedirect
    from plugins.installed.orders.models import OrderItem
    from plugins.installed.orders.refunds import ReturnRequest, ReturnService

    rr = get_object_or_404(
        ReturnRequest.objects.select_related('order', 'order__customer'),
        pk=rma_id,
    )
    error = ''
    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        try:
            if action == 'approve':
                ReturnService.approve(rr, decided_by=request.user)
            elif action == 'reject':
                ReturnService.reject(
                    rr,
                    decided_by=request.user,
                    staff_note=(request.POST.get('staff_note') or '')[:2000],
                )
            elif action == 'refund_money':
                ReturnService.mark_received_and_refund(
                    rr, actor=request.user, as_store_credit=False
                )
            elif action == 'refund_credit':
                ReturnService.mark_received_and_refund(rr, actor=request.user, as_store_credit=True)
            else:
                error = 'Unknown action.'
        except Exception as e:  # noqa: BLE001
            error = str(e)
        if not error:
            return HttpResponseRedirect(request.path)
        rr.refresh_from_db()

    line_items = []
    items_by_id = {str(oi.id): oi for oi in OrderItem.objects.filter(order=rr.order)}
    for entry in rr.items or []:
        oi = items_by_id.get(str(entry.get('order_item_id', '')))
        if oi:
            line_items.append(
                {
                    'order_item': oi,
                    'qty': int(entry.get('quantity', 0) or 0),
                }
            )
    return render(
        request,
        'admin_dashboard/return_detail.html',
        {
            'rr': rr,
            'line_items': line_items,
            'error': error,
            'active_nav': 'orders',
        },
    )


# ─── Bulk actions on list pages ───────────────────────────────────────────────
