"""Storefront view for the bulk CSV reorder uploader."""

from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

logger = logging.getLogger('morpheus.b2b.views_bulk_order')

MAX_UPLOAD_BYTES = 64 * 1024  # 64 KB — anything bigger isn't a CSV reorder


@login_required
@require_http_methods(['GET', 'POST'])
def bulk_order(request: HttpRequest) -> HttpResponse:
    from plugins.installed.b2b.services_bulk_order import (  # noqa: PLC0415
        apply_to_cart,
        parse_csv,
    )
    from plugins.installed.orders.services import CartService  # noqa: PLC0415

    if request.method == 'GET':
        return render(request, 'b2b/bulk_order.html', {'result': None})

    raw = (request.POST.get('rows') or '').strip()
    if not raw and 'file' in request.FILES:
        upload = request.FILES['file']
        if upload.size > MAX_UPLOAD_BYTES:
            return render(
                request,
                'b2b/bulk_order.html',
                {'result': None, 'error': 'File too large (64 KB max).'},
                status=413,
            )
        raw = upload.read().decode('utf-8', errors='replace')

    if not raw:
        return render(
            request,
            'b2b/bulk_order.html',
            {'result': None, 'error': 'Paste rows or upload a CSV.'},
            status=400,
        )

    parsed = parse_csv(raw)
    if not parsed:
        return render(
            request,
            'b2b/bulk_order.html',
            {
                'result': None,
                'error': 'No parseable rows found. Expected: SKU,quantity per line.',
            },
            status=400,
        )

    cart = CartService.get_or_create_cart(
        session_key=request.session.session_key or '',
        customer=request.user,
    )
    account = _resolve_account_for(request.user)
    result = apply_to_cart(cart=cart, parsed_rows=parsed, account=account)

    return render(
        request,
        'b2b/bulk_order.html',
        {'result': result, 'cart': cart},
    )


def _resolve_account_for(user):
    """Resolve a CRM Account for the user; None if no link exists."""
    try:
        from django.apps import apps  # noqa: PLC0415

        Account = apps.get_model('crm', 'Account')
        if Account is None:
            return None
        return Account.objects.filter(customer_email=getattr(user, 'email', '')).first()
    except Exception:  # noqa: BLE001
        logger.debug('b2b.bulk_order: account lookup failed', exc_info=True)
        return None
