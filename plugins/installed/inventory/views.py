"""Inventory storefront views.

Public, customer-facing endpoints exposed by the inventory plugin. Right
now: just the back-in-stock subscription form posted from the PDP.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

logger = logging.getLogger('morpheus.inventory')


@require_POST
def back_in_stock_subscribe(request: HttpRequest, product_id) -> HttpResponse:
    """Create a BackInStockSubscription for (product, email).

    Idempotent: get_or_create on (product, email) so a double-click or a
    second-tab POST doesn't crash on the unique constraint. Redirects to
    the PDP either way with a flash message.
    """
    from plugins.installed.catalog.models import Product  # noqa: PLC0415
    from plugins.installed.inventory.models import BackInStockSubscription  # noqa: PLC0415

    email = (request.POST.get('email') or '').strip()
    fallback_url = '/products/'

    try:
        product = Product.objects.only('id', 'slug').get(id=product_id)
    except Product.DoesNotExist:
        messages.error(request, "We couldn't find that title.")
        return redirect(fallback_url)

    pdp_url = f'/products/{product.slug}/'

    if not email:
        messages.error(request, 'Please enter an email address.')
        return redirect(pdp_url)

    try:
        customer = request.user if request.user.is_authenticated else None
        BackInStockSubscription.objects.get_or_create(
            product=product,
            email=email,
            variant=None,
            defaults={'customer': customer},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning('inventory: back_in_stock_subscribe failed: %s', e)
        messages.error(request, "Sorry — we couldn't save your subscription.")
        return redirect(pdp_url)

    messages.success(request, "We'll email you when this title is back.")
    return redirect(pdp_url)
