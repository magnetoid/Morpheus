"""Storefront view for a single Look.

The plugin has always advertised a look page at ``/looks/<slug>/`` — in its
description, and in the "See the full look" link the PDP block renders — but it
shipped with no ``urls.py`` and no view, so every one of those links 404'd. This
is that page.
"""

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render


def look_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """Render a published Look and the products in it (in author order)."""
    from plugins.installed.lookbook.models import Look  # noqa: PLC0415

    look = (
        Look.objects.filter(slug=slug, is_published=True).prefetch_related('items__product').first()
    )
    if look is None:
        raise Http404('Look not found.')

    # Walk the through-model so the merchant's ordering (LookItem.order) is
    # honoured; `Look.products` alone would come back in arbitrary order.
    products = [item.product for item in look.items.all() if item.product_id]
    return render(
        request,
        'lookbook/look_detail.html',
        {'look': look, 'products': products},
    )
