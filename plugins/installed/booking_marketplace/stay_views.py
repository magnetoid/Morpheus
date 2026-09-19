"""Storefront views for the accommodation (stays) engine."""

from __future__ import annotations

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from plugins.installed.booking_marketplace import seo_jsonld, stays
from plugins.installed.booking_marketplace.models import (
    AMENITY_LABELS,
    PROPERTY_TYPES,
    REGIONS,
    Property,
    RoomType,
)
from plugins.installed.booking_marketplace.services import BookingError
from plugins.installed.booking_marketplace.views import listing_mode, takes_enquiry_only


def _amenities(slugs):
    out = []
    for s in slugs or []:
        label, icon = AMENITY_LABELS.get(s, (s.replace('_', ' ').title(), 'check'))
        out.append({'slug': s, 'label': label, 'icon': icon})
    return out


def stays_index(request):
    qs = Property.objects.filter(is_active=True)
    region = request.GET.get('region') or ''
    ptype = request.GET.get('type') or ''
    if region:
        qs = qs.filter(region=region)
    if ptype:
        qs = qs.filter(property_type=ptype)
    return render(
        request,
        'booking_marketplace/stays/index.html',
        {
            'properties': qs,
            'listing_mode': listing_mode(),
            'active_region': region,
            'active_type': ptype,
            'region_choices': REGIONS,
            'type_choices': PROPERTY_TYPES,
            'seo_title': _('Hotels & stays in Montenegro'),
            'stays_jsonld': seo_jsonld.stays_index_jsonld(qs, request=request),
        },
    )


def stay_detail(request, slug):
    prop = get_object_or_404(
        Property.objects.prefetch_related('room_types', 'images'), slug=slug, is_active=True
    )
    return render(
        request,
        'booking_marketplace/stays/detail.html',
        {
            'property': prop,
            'room_types': prop.room_types.filter(is_active=True),
            'amenities': _amenities(prop.amenities),
            'listing_mode': listing_mode(),
            # Per-page SEO/AEO: feeds the shared seo_meta fallbacks + og:image.
            'seo_object': prop,
            'seo_title': f'{prop.name} · {prop.location or "Montenegro"}',
            'seo_description': (prop.short_description or prop.description)[:155],
            'seo_image': prop.image.url if prop.image else '',
            'seo_og_type': 'product',
            # LodgingBusiness/Hotel JSON-LD (prices gated to non-listing mode).
            'seo_jsonld': seo_jsonld.property_jsonld(
                prop, request=request, with_prices=not listing_mode()
            ),
        },
    )


def stay_quote(request, slug):
    room_type = get_object_or_404(
        RoomType, pk=request.GET.get('room_type'), property__slug=slug, is_active=True
    )
    try:
        q = stays.quote_stay(
            room_type,
            check_in=request.GET.get('check_in'),
            check_out=request.GET.get('check_out'),
            rooms=request.GET.get('rooms', 1),
            adults=request.GET.get('adults', 2),
            children=request.GET.get('children', 0),
        )
    except BookingError as e:
        return JsonResponse({'error': str(e)}, status=400)
    available = stays.room_availability(room_type, q['check_in'], q['check_out'])
    return JsonResponse(
        {
            'ok': True,
            'nights': q['nights'],
            'room_subtotal': str(q['room_subtotal'].amount),
            'service_fee': str(q['service_fee'].amount),
            'tourist_tax': str(q['tourist_tax'].amount),
            'total': str(q['total'].amount),
            'currency': q['currency'],
            'available': available,
        }
    )


def stay_book(request, slug):
    prop = get_object_or_404(Property, slug=slug, is_active=True)
    if request.method != 'POST':
        return redirect('booking_marketplace:stay_detail', slug=slug)
    room_type = get_object_or_404(
        RoomType, pk=request.POST.get('room_type'), property=prop, is_active=True
    )
    common = dict(
        check_in=request.POST.get('check_in'),
        check_out=request.POST.get('check_out'),
        rooms=request.POST.get('rooms', 1),
        adults=request.POST.get('adults', 2),
        children=request.POST.get('children', 0),
    )
    try:
        # Enquiry unless a payment step can actually charge. create_stay_booking
        # writes status='confirmed' and holds inventory under a row lock, and
        # nothing in that path takes money — so confirming for free would block a
        # host's rooms at no cost. See views.takes_enquiry_only().
        if takes_enquiry_only():
            stays.submit_stay_enquiry(
                property=prop,
                room_type=room_type,
                customer=request.user,
                name=request.POST.get('name', ''),
                email=request.POST.get('email', ''),
                phone=request.POST.get('phone', ''),
                message=request.POST.get('message', ''),
                **common,
            )
            messages.success(
                request, _("Thanks — we'll be in touch about availability and pricing.")
            )
        else:
            stays.create_stay_booking(
                room_type=room_type,
                customer=request.user if request.user.is_authenticated else None,
                customer_name=request.POST.get('name', ''),
                customer_email=request.POST.get('email', ''),
                customer_phone=request.POST.get('phone', ''),
                notes=request.POST.get('message', ''),
                **common,
            )
            messages.success(request, _('Your stay is booked! A confirmation is on its way.'))
    except BookingError as e:
        messages.error(request, str(e))
    return redirect('booking_marketplace:stay_detail', slug=slug)
