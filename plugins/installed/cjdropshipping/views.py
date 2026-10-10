"""CJdropshipping dashboard: connection, product finder, orders; and CJ's webhook."""

from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.authz import require_capability
from morpheus.app.views import render, staff_member_required

logger = logging.getLogger('morpheus.cjdropshipping.views')

PAGE = '/dashboard/apps/cjdropshipping/cj/'
_CONNECTION_KEY = 'cj:connection'


def _context(request: HttpRequest) -> dict:
    from plugins.installed.cjdropshipping.models import CJLink, CJOrder
    from plugins.installed.cjdropshipping.services.client import CJError, api_key
    from plugins.installed.cjdropshipping.services.orders import lines_for, orders_to_send

    has_key = bool(api_key())
    awaiting, search, search_error = [], None, ''
    if has_key:
        for order in orders_to_send()[:50]:
            lines, unmapped = lines_for(order)
            awaiting.append({'order': order, 'lines': len(lines), 'unmapped': unmapped})
        query = (request.GET.get('q') or '').strip()
        if query:
            from plugins.installed.cjdropshipping.services.catalog import search as cj_search

            try:
                search = cj_search(query, page=int(request.GET.get('page') or 1))
                search['query'] = query
            except (CJError, ValueError) as e:
                search_error = getattr(e, 'message', str(e))
    records = CJOrder.objects.select_related('order')
    return {
        'has_key': has_key,
        'connection': cache.get(_CONNECTION_KEY),
        'webhook_url': request.build_absolute_uri('/cj/webhook/'),
        'awaiting': awaiting,
        'unpaid': list(records.filter(status='created').order_by('-sent_at')[:100]),
        'in_progress': list(records.filter(status='paid').order_by('-sent_at')[:100]),
        'problems': list(
            records.filter(status__in=('failed', 'cancelled')).order_by('-updated_at')[:50]
        ),
        'shipped': list(records.filter(status='shipped').order_by('-shipped_at')[:25]),
        'links_count': CJLink.objects.count(),
        'search': search,
        'search_error': search_error,
        'active_nav': 'orders',
    }


@staff_member_required
@require_capability('orders.read')
def dashboard(request):
    return render(request, 'cjdropshipping/dashboard.html', _context(request))


@staff_member_required
@require_capability('orders.write')
@require_POST
def test_connection_view(request):
    from plugins.installed.cjdropshipping.services.client import CJError, credentials
    from plugins.installed.cjdropshipping.services.client import request as cj

    try:
        credentials(force=True)
        account = cj('GET', '/setting/get') or {}
        balance = cj('GET', '/shopping/pay/getBalance') or {}
    except CJError as e:
        cache.set(_CONNECTION_KEY, {'ok': False, 'error': e.message}, timeout=60 * 60)
        messages.error(request, f'CJ connection failed: {e.message}')
        return redirect(PAGE)
    snapshot = {
        'ok': True,
        'account': account.get('openName') or account.get('openEmail') or '',
        'qps': (account.get('setting') or {}).get('qpsLimit'),
        'balance': balance.get('amount'),
        'sandbox': bool(account.get('isSandbox')),
    }
    cache.set(_CONNECTION_KEY, snapshot, timeout=60 * 60)
    messages.success(request, f'Connected to CJ as {snapshot["account"] or "your account"}.')
    return redirect(PAGE)


@staff_member_required
@require_capability('orders.write')
@require_POST
def register_webhooks_view(request):
    from plugins.installed.cjdropshipping.services.client import CJError
    from plugins.installed.cjdropshipping.services.webhooks import register

    url = request.build_absolute_uri('/cj/webhook/')
    if not url.startswith('https://'):
        messages.error(request, 'CJ only calls https addresses; open the dashboard over https.')
        return redirect(PAGE)
    try:
        register(url)
    except CJError as e:
        messages.error(request, f'CJ did not accept the webhook: {e.message}')
    else:
        messages.success(request, f'CJ now reports orders, tracking, stock and prices to {url}.')
    return redirect(PAGE)


@staff_member_required
@require_capability('catalog.write')
@require_POST
def import_product_view(request):
    from plugins.installed.cjdropshipping.services.catalog import import_cj_product
    from plugins.installed.cjdropshipping.services.client import CJError

    pid = (request.POST.get('pid') or '').strip()
    if not pid:
        messages.error(request, 'Choose a CJ product to import.')
        return redirect(PAGE)
    try:
        result = import_cj_product(pid)
    except (CJError, ValueError) as e:
        messages.error(request, f'Import failed: {getattr(e, "message", str(e))}')
        return redirect(PAGE)
    note = (
        f' {len(result.image_errors)} photo(s) could not be fetched.' if result.image_errors else ''
    )
    messages.success(
        request,
        f'Imported "{result.product.name}" as a draft — review the price and publish it.{note}',
    )
    return redirect(f'/dashboard/products/{result.product.pk}/')


@staff_member_required
@require_capability('orders.write')
@require_POST
def send_order_view(request, order_number: str):
    from plugins.installed.cjdropshipping.services.orders import forward_order
    from plugins.installed.orders.models import Order

    order = get_object_or_404(Order, order_number=order_number)
    record = forward_order(order)
    if record is None:
        messages.info(request, f'Order #{order_number} is already with CJ.')
    elif record.status == 'failed':
        messages.error(request, f'Order #{order_number} was not sent: {record.note}')
    else:
        messages.success(
            request, f'Order #{order_number} is in CJ ({record.get_status_display()}).'
        )
    return redirect(PAGE)


@staff_member_required
@require_capability('orders.write')
@require_POST
def pay_order_view(request, order_number: str):
    from plugins.installed.cjdropshipping.models import CJOrder
    from plugins.installed.cjdropshipping.services.orders import pay

    record = get_object_or_404(CJOrder, order__order_number=order_number, status='created')
    problem = pay(record)
    if problem:
        messages.error(request, f'CJ did not take the payment: {problem}')
    else:
        messages.success(request, f'Order #{order_number} is paid from the CJ balance.')
    return redirect(PAGE)


@staff_member_required
@require_capability('orders.write')
@require_POST
def sync_view(request):
    from plugins.installed.cjdropshipping.services.client import CJError
    from plugins.installed.cjdropshipping.services.orders import sync_open_orders

    try:
        count = sync_open_orders()
    except CJError as e:
        messages.error(request, f'Refresh failed: {e.message}')
    else:
        messages.success(request, f'Refreshed {count} order(s) from CJ.')
    return redirect(PAGE)


@csrf_exempt
@require_POST
def webhook_view(request):
    """CJ's push. Always 200 (CJ closes a topic that fails); only a verified message acts."""
    from plugins.installed.cjdropshipping.services.client import CJError, api_key, open_id
    from plugins.installed.cjdropshipping.services.webhooks import apply, verify

    body = request.body
    outcome = 'ignored'
    if api_key():
        try:
            secret = open_id()
        except CJError as e:
            secret = ''
            logger.warning('cjdropshipping: webhook not verifiable: %s', e.message)
        if verify(body, request.headers.get('sign', ''), secret):
            try:
                outcome = apply(json.loads(body.decode('utf-8')))
            except (ValueError, UnicodeDecodeError):
                outcome = 'unreadable body'
            except Exception:  # noqa: BLE001 — answer 200 regardless; the sweep catches up
                logger.exception('cjdropshipping: webhook failed')
                outcome = 'error'
        else:
            outcome = 'unverified'
    logger.info('cjdropshipping: webhook %s', outcome)
    return JsonResponse({'ok': True})
