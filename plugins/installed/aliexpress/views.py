"""AliExpress dashboard: OAuth connect, product finder, orders."""

from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpRequest
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from core.authz import require_capability
from morpheus.app.views import render, staff_member_required

logger = logging.getLogger('morpheus.aliexpress.views')

PAGE = '/dashboard/apps/aliexpress/orders/'
CALLBACK_PATH = '/dashboard/aliexpress/oauth/callback/'
_STATE_KEY = 'aliexpress_oauth_state'


def _callback_url(request: HttpRequest) -> str:
    return request.build_absolute_uri(CALLBACK_PATH)


def _context(request: HttpRequest) -> dict:
    from django.utils import timezone

    from plugins.installed.aliexpress.models import AELink, AEOrder
    from plugins.installed.aliexpress.services.client import AEError, app_credentials, connection
    from plugins.installed.aliexpress.services.orders import lines_for, orders_to_send

    key, secret = app_credentials()
    conn = connection()
    awaiting, search, search_error = [], None, ''
    if conn['connected']:
        for order in orders_to_send()[:50]:
            lines, unmapped = lines_for(order)
            awaiting.append({'order': order, 'lines': len(lines), 'unmapped': unmapped})
        query = (request.GET.get('q') or '').strip()
        if query:
            from plugins.installed.aliexpress.services.catalog import search as ae_search

            try:
                search = ae_search(query, page=int(request.GET.get('page') or 1))
                search['query'] = query
            except (AEError, ValueError) as e:
                search_error = getattr(e, 'message', str(e))
    records = AEOrder.objects.select_related('order')
    now_ms = int(timezone.now().timestamp() * 1000)
    return {
        'has_app': bool(key and secret),
        'connection': conn,
        'token_days_left': max(0, (conn['access_expires_ms'] - now_ms) // 86_400_000)
        if conn['access_expires_ms']
        else None,
        'callback_url': _callback_url(request),
        'awaiting': awaiting,
        'to_pay': list(records.filter(status='placed').order_by('pay_by')[:100]),
        'in_progress': list(records.filter(status='paid').order_by('-sent_at')[:100]),
        'problems': list(
            records.filter(status__in=('failed', 'cancelled')).order_by('-updated_at')[:50]
        ),
        'shipped': list(records.filter(status='shipped').order_by('-shipped_at')[:25]),
        'links_count': AELink.objects.count(),
        'search': search,
        'search_error': search_error,
        'active_nav': 'orders',
    }


@staff_member_required
@require_capability('orders.read')
def dashboard(request):
    return render(request, 'aliexpress/dashboard.html', _context(request))


@staff_member_required
@require_capability('orders.write')
def oauth_start_view(request):
    """Send the merchant to AliExpress to authorise this store on their account."""
    from plugins.installed.aliexpress.services.client import AUTHORIZE_URL, app_credentials

    key, secret = app_credentials()
    if not key or not secret:
        messages.error(
            request,
            'Save the AliExpress AppKey and AppSecret first (Settings → Shipping → AliExpress).',
        )
        return redirect(PAGE)
    state = secrets.token_urlsafe(24)
    request.session[_STATE_KEY] = state
    query = urlencode(
        {
            'response_type': 'code',
            'force_auth': 'true',
            'redirect_uri': _callback_url(request),
            'client_id': key,
            'state': state,
        }
    )
    return redirect(f'{AUTHORIZE_URL}?{query}')


@staff_member_required
@require_capability('orders.write')
def oauth_callback_view(request):
    from plugins.installed.aliexpress.services.client import AEError, exchange_code

    expected = request.session.pop(_STATE_KEY, None)
    state, code = request.GET.get('state', ''), request.GET.get('code', '')
    if not expected or not secrets.compare_digest(str(expected), str(state)):
        messages.error(
            request, 'That AliExpress answer did not come from this page — connect again.'
        )
        return redirect(PAGE)
    if not code:
        messages.error(request, 'AliExpress did not authorise the account.')
        return redirect(PAGE)
    try:
        tokens = exchange_code(code)
    except AEError as e:
        messages.error(request, f'AliExpress refused the connection: {e.message}')
        return redirect(PAGE)
    messages.success(request, f'Connected to AliExpress as {tokens["_account"] or "your account"}.')
    return redirect(PAGE)


@staff_member_required
@require_capability('orders.write')
@require_POST
def disconnect_view(request):
    from plugins.installed.aliexpress.services.client import disconnect

    disconnect()
    messages.success(request, 'AliExpress disconnected. Orders already placed stay in the list.')
    return redirect(PAGE)


@staff_member_required
@require_capability('catalog.write')
@require_POST
def import_product_view(request):
    from plugins.installed.aliexpress.services.catalog import import_ae_product
    from plugins.installed.aliexpress.services.client import AEError

    product_id = (request.POST.get('product_id') or '').strip()
    if not product_id.isdigit():
        messages.error(request, 'Choose an AliExpress product to import.')
        return redirect(PAGE)
    try:
        result = import_ae_product(product_id)
    except (AEError, ValueError) as e:
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
    from plugins.installed.aliexpress.services.orders import forward_order
    from plugins.installed.orders.models import Order

    order = get_object_or_404(Order, order_number=order_number)
    record = forward_order(order)
    if record is None:
        messages.info(request, f'Order #{order_number} is already on AliExpress.')
    elif record.status == 'failed':
        messages.error(request, f'Order #{order_number} was not placed: {record.note}')
    else:
        messages.success(request, f'Order #{order_number} is placed on AliExpress — pay it there.')
    return redirect(PAGE)


@staff_member_required
@require_capability('orders.write')
@require_POST
def sync_view(request):
    from plugins.installed.aliexpress.services.orders import sync_open_orders

    count = sync_open_orders()
    messages.success(request, f'Read {count} order(s) from AliExpress.')
    return redirect(PAGE)
