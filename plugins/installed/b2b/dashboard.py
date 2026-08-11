"""B2B dashboard pages (admin-only).

Provides a creation path for `PriceList` rows and per-list `PriceListItem`
management. Without this, `PriceListItem` could never be created because
its parent had no UI.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from morpheus.app import dashboard_trail

logger = logging.getLogger('morpheus.b2b')


def _trail(*items):
    return dashboard_trail('B2B', '/dashboard/apps/b2b/pricelists/', *items)


@staff_member_required
def pricelists(request):
    """List PriceLists + form to create a new one."""
    from plugins.installed.b2b.models import PriceList  # noqa: PLC0415

    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        description = (request.POST.get('description') or '').strip()
        is_default = request.POST.get('is_default') == 'on'
        if not name:
            messages.error(request, 'Name is required.')
        elif PriceList.objects.filter(name=name).exists():
            messages.error(request, f'A price list named "{name}" already exists.')
        else:
            pl = PriceList.objects.create(
                name=name,
                description=description,
                is_default=is_default,
            )
            messages.success(request, f'Created price list "{pl.name}".')
            return HttpResponseRedirect(reverse('b2b_dashboard:pricelist_detail', args=[pl.id]))
        return HttpResponseRedirect(request.path)

    rows = list(PriceList.objects.all()[:200])
    return render(
        request,
        'b2b/dashboard/pricelists.html',
        {
            'pricelists': rows,
            'active_nav': 'b2b',
            'breadcrumb_trail': _trail({'label': 'Price lists'}),
        },
    )


def _handle_item_post(request, pricelist) -> None:
    """Process add / edit / delete actions on PriceListItem rows."""
    from plugins.installed.b2b.models import PriceListItem  # noqa: PLC0415
    from plugins.installed.catalog.models import Product, ProductVariant  # noqa: PLC0415

    action = request.POST.get('action', '')

    if action == 'delete_item':
        item_id = request.POST.get('item_id', '')
        try:
            PriceListItem.objects.filter(price_list=pricelist, pk=item_id).delete()
            messages.success(request, 'Item removed.')
        except (ValueError, PriceListItem.DoesNotExist):
            messages.error(request, 'Item not found.')
        return

    if action == 'add_item':
        product_id = (request.POST.get('product_id') or '').strip()
        variant_id = (request.POST.get('variant_id') or '').strip() or None
        price_raw = (request.POST.get('price') or '').strip()
        try:
            product = Product.objects.get(pk=product_id)
        except (Product.DoesNotExist, ValueError):
            messages.error(request, 'Pick a product first.')
            return
        try:
            price = Decimal(price_raw)
            if price < 0:
                raise InvalidOperation()
        except (InvalidOperation, ValueError):
            messages.error(request, 'Price must be a non-negative decimal.')
            return
        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(pk=variant_id)
            except (ProductVariant.DoesNotExist, ValueError):
                messages.error(request, 'Variant not found.')
                return
        currency = (request.POST.get('currency') or 'USD').strip() or 'USD'
        try:
            PriceListItem.objects.create(
                price_list=pricelist,
                product=product,
                variant=variant,
                price=(price, currency),
            )
            messages.success(request, f'Added {product.name}.')
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f'Could not add item: {exc}')
        return


@staff_member_required
def pricelist_detail(request, pricelist_id):
    """Show items on a price list + form to add / edit / delete rows."""
    from plugins.installed.b2b.models import PriceList  # noqa: PLC0415
    from plugins.installed.catalog.models import Product  # noqa: PLC0415

    pricelist = get_object_or_404(PriceList, pk=pricelist_id)

    if request.method == 'POST':
        _handle_item_post(request, pricelist)
        return HttpResponseRedirect(request.path)

    items = list(pricelist.items.select_related('product', 'variant').order_by('product__name'))

    # Lightweight product picker — top 100 active products by name.
    product_pick = list(
        Product.objects.filter(status='active').order_by('name').values('id', 'name')[:100]
    )

    return render(
        request,
        'b2b/dashboard/pricelist_detail.html',
        {
            'pricelist': pricelist,
            'items': items,
            'product_pick': product_pick,
            'active_nav': 'b2b',
            'breadcrumb_trail': _trail(
                {'label': 'Price lists', 'url': '/dashboard/apps/b2b/pricelists/'},
                {'label': pricelist.name},
            ),
        },
    )
