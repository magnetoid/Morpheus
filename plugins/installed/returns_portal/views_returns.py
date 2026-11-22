"""The customer's returns and exchanges (C4, v0.188.0).

``/account/orders/<n>/return/`` asks for a return, ``/account/returns/`` lists a
signed-in customer's returns, ``/account/returns/<id>/`` shows one, and
``/returns/start/`` lets a guest in by order number and email (both must match; a
wrong pair reads exactly like an unknown number). The form and the status page
answer the order's owner, or anyone holding the order's ``public_token`` from an
email link, remembered in the session as the withdrawal pages do.

The record and its rules are ``orders``': ``orders.returns.returnable_lines``
decides what may come back and ``ReturnService.create_request`` checks it again
with the order locked. This app records what the customer chose
(``ReturnResolution``).
"""

from __future__ import annotations

import logging
import secrets

from django.http import Http404
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from morpheus.app.views import redirect, render

logger = logging.getLogger('morpheus.returns_portal')

#: Session key: the orders this visitor reached by number + email or a token link.
_KNOWN = 'returns_orders'
_SEO = {'seo_title': 'Return or exchange', 'seo_noindex_reason': 'a form about one order'}

REASON_TEXT = {
    'not_paid': 'Not paid yet',
    'not_sent': 'Not sent yet',
    'does_not_ship': 'A download or a service',
    'window_closed': 'Past the return window',
    'already_returned': 'Already being returned',
    'exchange_order': 'An exchange: please contact us',
}


def _remember(request, order) -> None:
    known = [pk for pk in request.session.get(_KNOWN, []) if pk != str(order.pk)]
    request.session[_KNOWN] = [*known[-9:], str(order.pk)]


def _may_see(request, order) -> bool:
    """The owner, or a visitor holding this order's link or details. A ``token``
    in the address that names this order is remembered for the session."""
    if request.user.is_authenticated and order.customer_id == request.user.pk:
        return True
    token = (request.GET.get('token') or '').strip()
    if token:
        if secrets.compare_digest(token, order.public_token or ''):
            _remember(request, order)
            return True
        return False
    return str(order.pk) in request.session.get(_KNOWN, [])


def _order_or_404(request, order_number):
    from plugins.installed.orders.models import Order  # noqa: PLC0415

    order = Order.objects.filter(order_number__iexact=order_number).first()
    if order is None:
        raise Http404('Order not found')
    return order


def _window() -> int:
    from plugins.installed.returns_portal.seo_graph import window_days  # noqa: PLC0415

    return window_days()


def _lines(order):
    from plugins.installed.orders.returns import returnable_lines  # noqa: PLC0415
    from plugins.installed.returns_portal.policy import exchange_editions  # noqa: PLC0415

    rows = []
    for line in returnable_lines(order, window_days=_window()):
        rows.append(
            {
                'line': line,
                'item': line.item,
                'units': line.units,
                'why_not': REASON_TEXT.get(line.reason, ''),
                'editions': exchange_editions(line.item) if line.units else [],
            }
        )
    return rows


def _parse(request, order, rows, offered):
    """(items, outcome, exchange choices, error) from the posted form."""
    outcome = (request.POST.get('outcome') or 'refund').strip()
    if outcome not in offered:
        return None, outcome, [], 'Choose how you would like it resolved.'
    items, choices = [], []
    for row in rows:
        item = row['item']
        try:
            qty = int(request.POST.get(f'qty_{item.pk}') or 0)
        except ValueError:
            qty = 0
        if qty <= 0:
            continue
        if qty > row['units']:
            return None, outcome, [], 'Those items can no longer be returned.'
        items.append({'order_item_id': str(item.pk), 'quantity': qty})
        if outcome == 'exchange':
            wanted = (request.POST.get(f'edition_{item.pk}') or '').strip()
            if wanted not in {str(v.pk) for v in row['editions']}:
                return None, outcome, [], 'Choose an edition to exchange each item for.'
            choices.append({'order_item_id': str(item.pk), 'exchange_variant_id': wanted})
    if not items:
        return None, outcome, [], 'Choose at least one item to send back.'
    return items, outcome, choices, ''


@never_cache
@require_http_methods(['GET', 'POST'])
def return_form(request, order_number):
    """Ask for a return or an exchange of the lines that may come back."""
    from plugins.installed.orders.refunds import ReturnService  # noqa: PLC0415
    from plugins.installed.orders.returns import ReturnRefused  # noqa: PLC0415
    from plugins.installed.returns_portal import policy  # noqa: PLC0415
    from plugins.installed.returns_portal.models import ReturnResolution  # noqa: PLC0415

    order = _order_or_404(request, order_number)
    if not _may_see(request, order):
        if request.user.is_authenticated or request.GET.get('token'):
            raise Http404('Order not found')
        return redirect(reverse('returns_portal:returns_start'))
    signed_in = request.user.is_authenticated and order.customer_id == request.user.pk
    offered = policy.offered_outcomes(order, signed_in=signed_in)
    rows = _lines(order)
    error = ''
    if request.method == 'POST':
        items, outcome, choices, error = _parse(request, order, rows, offered)
        if not error:
            try:
                rr = ReturnService.create_request(
                    order=order,
                    items=items,
                    reason=(request.POST.get('reason') or 'other')[:25],
                    customer_note=(request.POST.get('note') or '')[:2000],
                    requested_by=request.user if request.user.is_authenticated else None,
                    window_days=_window(),
                )
            except ReturnRefused as e:
                error = str(e)
                rows = _lines(order)
            else:
                ReturnResolution.objects.create(
                    request=rr, resolution=outcome, exchange_choices=choices
                )
                return redirect(reverse('returns_portal:return_status', args=[rr.pk]))
    reasons = [(k, v) for k, v in _reason_choices() if k != 'withdrawal']
    return render(
        request,
        'returns_portal/return_form.html',
        {
            'order': order,
            'rows': rows,
            'returnable': [r for r in rows if r['units']],
            'offered': offered,
            'outcome_labels': policy.OUTCOME_LABELS,
            'reasons': reasons,
            'return_fee': policy.return_fee(order),
            'exchange_fee': policy.exchange_fee(order),
            'error': error,
            **_SEO,
        },
    )


def _reason_choices():
    from plugins.installed.orders.refunds import ReturnRequest  # noqa: PLC0415

    return ReturnRequest.REASON_CHOICES


@never_cache
def returns_list(request):
    """A signed-in customer's returns."""
    from plugins.installed.orders.refunds import ReturnRequest  # noqa: PLC0415

    if not request.user.is_authenticated:
        return redirect(f'/auth/login/?next={request.path}')
    returns = ReturnRequest.objects.filter(order__customer=request.user).select_related('order')
    return render(
        request,
        'returns_portal/returns_list.html',
        {'returns': list(returns), 'seo_title': 'Returns', 'seo_noindex_reason': 'an account page'},
    )


_STEPS = [
    ('requested', 'Requested'),
    ('approved', 'Approved'),
    ('received', 'Received'),
    ('refunded', 'Closed'),
]


@never_cache
def return_status(request, rma_id):
    """One return: where it stands, and what happens next."""
    from plugins.installed.orders.models import OrderItem  # noqa: PLC0415
    from plugins.installed.orders.refunds import ReturnRequest  # noqa: PLC0415
    from plugins.installed.returns_portal import policy  # noqa: PLC0415
    from plugins.installed.returns_portal.models import ReturnResolution  # noqa: PLC0415

    rr = ReturnRequest.objects.select_related('order').filter(pk=rma_id).first()
    if rr is None or not _may_see(request, rr.order):
        raise Http404('Return not found')
    keys = [k for k, _l in _STEPS]
    current = keys.index(rr.state) if rr.state in keys else -1
    steps = [
        {'key': k, 'label': label, 'done': current > i, 'current': current == i}
        for i, (k, label) in enumerate(_STEPS)
    ]
    items = {str(o.pk): o for o in OrderItem.objects.filter(order=rr.order)}
    lines = [
        {'item': items[str(e.get('order_item_id'))], 'quantity': e.get('quantity', 0)}
        for e in rr.items or []
        if str(e.get('order_item_id')) in items
    ]
    resolution = ReturnResolution.objects.filter(request=rr).first()
    return render(
        request,
        'returns_portal/return_status.html',
        {
            'rma': rr,
            'order': rr.order,
            'steps': steps,
            'lines': lines,
            'resolution': resolution,
            'outcome_label': policy.OUTCOME_LABELS.get(getattr(resolution, 'resolution', ''), ''),
            'instructions': policy.return_instructions() if rr.state == 'approved' else '',
            'is_closed': rr.state in ('refunded', 'cancelled', 'rejected'),
            'seo_title': 'Return status',
            'seo_noindex_reason': 'a page about one return',
        },
    )


@never_cache
@require_http_methods(['GET', 'POST'])
def returns_start(request):
    """A guest finds their order by its number and their email."""
    from core import bot_check  # noqa: PLC0415
    from plugins.installed.orders.withdrawal import find_order  # noqa: PLC0415
    from plugins.installed.returns_portal.views import _throttled  # noqa: PLC0415

    draft = {'number': '', 'email': ''}
    error, not_found = '', False
    if request.method == 'POST':
        draft = {
            'number': (request.POST.get('order_number') or '').strip()[:20],
            'email': (request.POST.get('email') or '').strip()[:254],
        }
        if _throttled(request, 'returns'):
            error = 'Too many tries. Please wait an hour and try again.'
        elif not bot_check.passes(request, 'withdrawal'):
            error = str(bot_check.REFUSED)
        else:
            order = find_order(draft['number'], draft['email'])
            if order is not None:
                _remember(request, order)
                return redirect(reverse('returns_portal:return_form', args=[order.order_number]))
            not_found = True
    return render(
        request,
        'returns_portal/returns_start.html',
        {'draft': draft, 'error': error, 'not_found': not_found, **_SEO},
    )


def order_return_action(order) -> bool:
    """Whether the order page offers "Return or exchange": something can come back."""
    from plugins.installed.orders.returns import returnable_lines  # noqa: PLC0415

    try:
        return any(line.units for line in returnable_lines(order, window_days=_window()))
    except Exception:  # noqa: BLE001 — the order page never fails over it
        logger.warning('returns_portal: return action check failed', exc_info=True)
        return False


#: The order email's link to the return form.
EMAIL_LINK_LABEL = 'Return or exchange'


def on_order_email_links(value, order=None, key='', **kwargs):
    """ORDER_EMAIL_LINKS: an order with something that ships links its return form,
    opened by the order's token. Not an exchange order: it is not returned online."""
    from core.utils.site import site_base_url  # noqa: PLC0415
    from plugins.installed.orders.services import line_ships  # noqa: PLC0415

    if order is None or not getattr(order, 'public_token', ''):
        return value
    if (order.metadata or {}).get('exchange_of'):
        return value
    if not any(line_ships(item) for item in order.items.select_related('product', 'variant')):
        return value
    path = reverse('returns_portal:return_form', args=[order.order_number])
    url = f'{site_base_url().rstrip("/")}{path}?token={order.public_token}'
    value.append({'label': EMAIL_LINK_LABEL, 'url': url})
    return value
