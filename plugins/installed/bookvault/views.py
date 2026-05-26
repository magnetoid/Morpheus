"""Dashboard views for the Bookvault plugin.

Five admin entry points:

  * ``overview``           Status card + product link audit + reauth.
  * ``connect``            POST → hit auth.bookvault.app/api/WooAuth,
                           persist the minted token into PluginConfig.
  * ``resend_order``       POST → re-POST an order to BV's
                           /woocommerce/orders/create endpoint.
  * ``bulk_link_products`` POST product_ids → 302 to BV's hosted
                           Bulk Products linker.
  * ``webhook_product_link`` POST from BV — writes back
                           ``locations`` + ``is_linked`` onto a
                           ``BookvaultProductLink`` row. Auth: shared
                           HMAC over the request body (BV signs).
"""
from __future__ import annotations

import hmac
import json
import logging
from hashlib import sha256
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger('morpheus.bookvault')


@staff_member_required
def overview(request: HttpRequest) -> HttpResponse:
    """Status card + product-link audit + reauth button."""
    from plugins.installed.bookvault.models import (
        BookvaultOrderLink, BookvaultProductLink,
    )
    from plugins.installed.bookvault.services import (
        _config, authorize_url, portal_apps_url, portal_orders_url, store_url,
    )

    cfg = _config()
    recent_orders = list(
        BookvaultOrderLink.objects
        .select_related('order')
        .order_by('-last_sent_at')[:25]
    )
    link_counts = {
        'linked': BookvaultProductLink.objects.filter(is_linked=True).count(),
        'pending': BookvaultProductLink.objects.filter(is_linked=False).count(),
    }
    return render(request, 'bookvault/overview.html', {
        'cfg': cfg,
        'store_url': store_url(),
        'recent_orders': recent_orders,
        'link_counts': link_counts,
        'portal_apps_url': portal_apps_url(),
        'portal_orders_url': portal_orders_url(),
        'register_url': authorize_url(action='register'),
        'login_url': authorize_url(),
        'active_nav': 'bookvault',
        'breadcrumb_trail': [
            {'label': 'Dashboard', 'url': '/dashboard/'},
            {'label': 'Bookvault'},
        ],
    })


@staff_member_required
@require_http_methods(['POST'])
def disconnect(request: HttpRequest) -> HttpResponseRedirect:
    """Tell BV to clean up + clear local credentials. Equivalent to
    the WP plugin's uninstall.php — but as an explicit admin action,
    not a plugin-delete side effect, so the merchant can resurrect
    the connection without re-installing the plugin."""
    from plugins.installed.bookvault.services import disconnect as svc_disconnect

    result = svc_disconnect()
    if 'error' in result:
        messages.warning(
            request,
            'Local credentials cleared. BV uninstall webhook failed: '
            + str(result['error']),
        )
    else:
        messages.success(request, 'Disconnected from Bookvault.')
    return HttpResponseRedirect('/dashboard/apps/bookvault/')


@staff_member_required
@require_http_methods(['POST'])
def connect(request: HttpRequest) -> HttpResponseRedirect:
    """Mint a fresh BV token. Falls through to the overview page with
    a flash message describing whether the handshake worked."""
    from plugins.installed.bookvault.services import authenticate

    override = (request.POST.get('store_url') or '').strip()
    data = authenticate(store_url_override=override)
    if 'error' in data:
        messages.error(request, f'Bookvault connect failed: {data["error"]}')
    elif data.get('Token') and data.get('StoreID'):
        messages.success(
            request,
            f'Connected to Bookvault as store {data.get("StoreID")}.',
        )
    else:
        messages.warning(
            request,
            'Bookvault responded but didn\'t return a Token / StoreID — '
            'check that this store\'s URL matches the one you registered '
            'at bookvault.app.',
        )
    return HttpResponseRedirect('/dashboard/apps/bookvault/')


@staff_member_required
@require_http_methods(['POST'])
def resend_order(request: HttpRequest, order_id) -> HttpResponseRedirect:
    """Manual "Resend Order To Bookvault" — mirrors the WP plugin's
    per-order admin action."""
    from plugins.installed.orders.models import Order
    from plugins.installed.bookvault.services import send_order

    order = get_object_or_404(Order, pk=order_id)
    result = send_order(order=order)
    if 'error' in result:
        messages.error(request, f'BV resend failed: {result["error"]}')
    else:
        messages.success(
            request,
            f'Order {order.order_number or order.id} sent to Bookvault.',
        )
    return HttpResponseRedirect(
        request.META.get('HTTP_REFERER') or '/dashboard/apps/bookvault/',
    )


@staff_member_required
@require_http_methods(['POST'])
def bulk_link_products(request: HttpRequest) -> HttpResponseRedirect:
    """302 to BV's hosted Bulk Products linker with the selected
    product IDs in the query string.

    Accepts both ``ids`` (the admin products-list bulk-form field
    name) and ``product_id`` (the dashboard overview's direct-link
    field name) so this view is callable from either surface."""
    from plugins.installed.bookvault.services import bulk_products_link

    ids = request.POST.getlist('ids') or request.POST.getlist('product_id')
    if not ids:
        messages.warning(request, 'No products selected.')
        return HttpResponseRedirect('/dashboard/apps/bookvault/')
    return HttpResponseRedirect(bulk_products_link(ids))


@csrf_exempt
@require_http_methods(['POST'])
def webhook_product_link(request: HttpRequest) -> JsonResponse:
    """Inbound BV webhook — sets locations + is_linked on a product/variant.

    BV signs the body with the shared client token; we verify via
    HMAC-SHA256 in ``X-BV-Signature``. Reject on mismatch — never let
    an unauthenticated POST mutate link state."""
    from plugins.installed.bookvault.models import BookvaultProductLink
    from plugins.installed.bookvault.services import _config

    cfg = _config()
    token = cfg.get('token', '')
    if not token:
        return JsonResponse({'error': 'bookvault not configured'}, status=503)

    signature = request.headers.get('X-BV-Signature', '')
    expected = hmac.new(
        token.encode('utf-8'), request.body, sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return JsonResponse({'error': 'bad signature'}, status=401)

    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid JSON'}, status=400)

    product_id = payload.get('product_id')
    variant_id = payload.get('variant_id') or None
    locations = payload.get('locations') or []
    is_linked = bool(payload.get('is_linked'))
    bv_title_id = (payload.get('bv_title_id') or '')[:64]
    if not product_id:
        return JsonResponse({'error': 'product_id is required'}, status=400)

    from plugins.installed.catalog.models import Product, ProductVariant

    product = Product.objects.filter(pk=product_id).first()
    if product is None:
        return JsonResponse({'error': 'product not found'}, status=404)
    variant = None
    if variant_id:
        variant = ProductVariant.objects.filter(pk=variant_id).first()

    link, _ = BookvaultProductLink.objects.update_or_create(
        product=product, variant=variant,
        defaults={
            'locations': list(locations) if isinstance(locations, list) else [],
            'is_linked': is_linked,
            'bv_title_id': bv_title_id,
        },
    )
    return JsonResponse({
        'ok': True, 'id': str(link.id),
        'is_linked': link.is_linked,
        'locations': link.locations,
    })
