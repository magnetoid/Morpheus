"""Auto-split from the legacy admin_dashboard/views.py monolith."""

from __future__ import annotations

from core.authz import require_capability
from morpheus.app.views import (
    HttpRequest,
    HttpResponse,
    get_object_or_404,
    render,
    staff_member_required,
)


@staff_member_required
@require_capability('orders.read')
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


def _resolution(rr) -> dict | None:
    """What the customer chose (RETURN_RESOLUTION), answered by the returns
    portal while it is on; None without one."""
    from core.hooks import MorpheusEvents, hook_registry

    try:
        found = hook_registry.filter(MorpheusEvents.RETURN_RESOLUTION, None, return_request=rr)
    except Exception:  # noqa: BLE001 — the page shows the plain form instead
        return None
    return found if isinstance(found, dict) and found.get('outcome') else None


def _fee(raw: str, currency: str):
    """The fee staff typed: blank is nothing, anything else a positive amount."""
    from decimal import Decimal, InvalidOperation

    from djmoney.money import Money

    raw = (raw or '').strip()
    if not raw:
        return Money(0, currency)
    try:
        amount = Decimal(raw)
    except InvalidOperation as e:
        raise ValueError('Enter the fee as an amount, such as 4.50.') from e
    if amount < 0 or not amount.is_finite():
        raise ValueError('Enter the fee as an amount, such as 4.50.')
    return Money(amount.quantize(Decimal('0.01')), currency)


def _posted_fee(request, outcome, resolution, currency):
    """The fee to take: what staff typed, except that an untouched box keeps the
    fee of the outcome it was filled for, so switching outcome takes the new
    outcome's fee (a refund never carries the exchange fee by accident)."""
    raw = request.POST.get('fee', '')
    prefilled_for = (request.POST.get('prefill_outcome') or '').strip()
    if (
        resolution
        and prefilled_for
        and outcome != prefilled_for
        and raw.strip() == (request.POST.get('prefill_fee') or '').strip()
    ):
        from djmoney.money import Money

        return (resolution.get('fees') or {}).get(outcome) or Money(0, currency)
    return _fee(raw, currency)


#: The old close buttons, kept for a release so an open tab still works.
_OLD_CLOSE = {'refund_money': 'refund', 'refund_credit': 'store_credit'}


def _act(request, rr, resolution, currency) -> str:
    """Carry out a POST on the return page; the error to show, or ''."""
    from plugins.installed.orders.refunds import ReturnService

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
        elif action == 'close' or action in _OLD_CLOSE:
            outcome = _OLD_CLOSE.get(action) or (request.POST.get('outcome') or 'refund')
            if outcome == 'exchange' and not (resolution and resolution['exchange']):
                raise ValueError('This return has no exchange to send.')
            ReturnService.close(
                rr,
                outcome=outcome,
                actor=request.user,
                exchange=resolution['exchange'] if outcome == 'exchange' else None,
                fee=_posted_fee(request, outcome, resolution, currency),
            )
        else:
            return 'Unknown action.'
    except Exception as e:  # noqa: BLE001
        return str(e)
    return ''


@staff_member_required
@require_capability('orders.write')
def return_detail(request: HttpRequest, rma_id) -> HttpResponse:
    from morpheus.app.views import HttpResponseRedirect
    from plugins.installed.catalog.models import ProductVariant
    from plugins.installed.orders.models import OrderItem
    from plugins.installed.orders.refunds import ReturnRequest

    rr = get_object_or_404(
        ReturnRequest.objects.select_related('order', 'order__customer'),
        pk=rma_id,
    )
    resolution = _resolution(rr)
    currency = str(rr.order.total.currency)
    error = ''
    if request.method == 'POST':
        error = _act(request, rr, resolution, currency)
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
    exchanges = []
    if resolution and resolution['exchange']:
        variants = {
            str(v.pk): v
            for v in ProductVariant.objects.filter(
                pk__in=[line.variant_id for line in resolution['exchange']]
            )
        }
        for line in resolution['exchange']:
            oi = items_by_id.get(str(line.order_item_id))
            if oi is not None:
                exchanges.append({'order_item': oi, 'variant': variants.get(str(line.variant_id))})
    can_exchange = bool(exchanges)
    chosen = resolution['outcome'] if resolution else 'refund'
    if chosen == 'exchange' and not can_exchange:
        chosen = 'refund'
    # The box shows the fee of the outcome it preselects.
    fee = (resolution.get('fees') or {}).get(chosen, resolution['fee']) if resolution else None
    return render(
        request,
        'admin_dashboard/return_detail.html',
        {
            'rr': rr,
            'line_items': line_items,
            'resolution': resolution,
            'exchanges': exchanges,
            'can_exchange': can_exchange,
            'can_credit': rr.order.customer_id is not None,
            'chosen': chosen,
            'fee_value': f'{fee.amount:.2f}' if fee is not None and fee.amount > 0 else '',
            'currency': currency,
            'error': error,
            'active_nav': 'orders',
        },
    )


# ─── Bulk actions on list pages ───────────────────────────────────────────────
