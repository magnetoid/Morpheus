"""Marketplace listings in the dashboard (Products → Listings).

A marketplace store sells experiences and local goods as listings, and the dashboard
had no page for them: the owner could not see or edit what the storefront sells, and
the staff bar's Edit led to the host's editor on the storefront (2026-10-14). Hosts
keep the host portal; store staff edit every host's listings here.
"""

from __future__ import annotations

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.authz import enforce, require_capability
from morpheus.app.views import staff_member_required
from plugins.installed.booking_marketplace.forms import ListingForm
from plugins.installed.booking_marketplace.models import BookableService

LIST_URL = '/dashboard/apps/booking_marketplace/listings/'

_KINDS = {'experience': 'Experiences', 'product': 'Local goods'}


def edit_url(service) -> str:
    # A listing linked to its catalog Product is edited in the product editor (with the
    # Booking details card); one not linked yet still has the listing editor.
    if service.product_id:
        return f'/dashboard/products/{service.product_id}/'
    return f'/dashboard/listings/{service.pk}/edit/'


@staff_member_required
@require_capability('catalog.read')
def listings_list(request):
    kind = request.GET.get('kind', '')
    state = request.GET.get('state', '')
    q = (request.GET.get('q') or '').strip()
    qs = BookableService.objects.select_related('vendor', 'category')
    if kind in _KINDS:
        qs = qs.filter(listing_kind=kind)
    if state == 'active':
        qs = qs.filter(is_active=True)
    elif state == 'inactive':
        qs = qs.filter(is_active=False)
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(location__icontains=q) | Q(vendor__name__icontains=q)
        )
    listings = list(qs.order_by('listing_kind', 'name')[:500])
    counts = {
        'all': BookableService.objects.count(),
        **{k: BookableService.objects.filter(listing_kind=k).count() for k in _KINDS},
    }
    return render(
        request,
        'booking_marketplace/dashboard/listings.html',
        {
            'listings': listings,
            'kinds': _KINDS,
            'kind': kind,
            'state': state,
            'q': q,
            'counts': counts,
            'edit_url': edit_url,
        },
    )


def _form_page(request, service):
    if request.method == 'POST':
        if (denied := enforce(request, 'catalog.write')) is not None:
            return denied
        form = ListingForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            saved = form.save()
            messages.success(request, f'Saved “{saved.name}”.')
            return redirect(edit_url(saved))
        messages.error(request, 'Some fields need fixing, see below.')
    else:
        form = ListingForm(instance=service)
    return render(
        request,
        'booking_marketplace/dashboard/listing_form.html',
        {
            'form': form,
            'service': service if service and service.pk else None,
            'list_url': LIST_URL,
            'breadcrumb_trail': [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Listings', 'url': LIST_URL},
                {'label': service.name if service and service.pk else 'New listing'},
            ],
        },
    )


@staff_member_required
@require_capability('catalog.read')
def listing_edit(request, pk):
    return _form_page(request, get_object_or_404(BookableService, pk=pk))


@staff_member_required
@require_capability('catalog.read')
def listing_new(request):
    return _form_page(request, BookableService())
