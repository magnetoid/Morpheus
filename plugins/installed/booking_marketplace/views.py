"""Booking marketplace — storefront views (only wired while the plugin is on).

Two operating modes (parity with the reference montenegro-experience-hub):
- LISTING mode (default, BOOKING_LISTING_MODE=True): prices hidden, the detail
  page shows a "Contact for price" enquiry form → submit_enquiry.
- MARKETPLACE mode: prices shown, the detail page shows a date + guests booking
  form → create_booking (server-derived totals + capacity check).
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from plugins.installed.booking_marketplace.models import REGIONS, BookableService, Place
from plugins.installed.booking_marketplace.services import (
    BookingError,
    available_dates,
    available_sessions,
    can_review,
    create_booking,
    create_review,
    review_summary,
    submit_enquiry,
)


def listing_mode() -> bool:
    """Year-1 directory mode (no prices/payments). Defaults to True."""
    return getattr(settings, 'BOOKING_LISTING_MODE', True)


def services_list(request):
    """Browse bookable experiences across all hosts."""
    services = (
        BookableService.objects.filter(
            is_active=True, vendor__is_active=True, listing_kind='experience'
        )
        .select_related('vendor', 'category')
    )
    region = (request.GET.get('region') or '').strip()
    if region:
        services = services.filter(region=region)
    q = (request.GET.get('q') or '').strip()
    if q:
        services = services.filter(
            Q(name__icontains=q)
            | Q(short_description__icontains=q)
            | Q(description__icontains=q)
            | Q(location__icontains=q)
        )
    category = (request.GET.get('category') or '').strip()
    if category:
        services = services.filter(category__name__icontains=category)
    sort = (request.GET.get('sort') or 'recommended').strip()
    order = {
        'recommended': ('-is_bestseller', '-rating', '-review_count'),
        'rating': ('-rating', '-review_count'),
        'price_low': ('price',),
        'price_high': ('-price',),
        'newest': ('-id',),
    }.get(sort, ('-is_bestseller', '-rating', '-review_count'))
    services = services.order_by(*order)
    return render(
        request,
        'booking_marketplace/list.html',
        {
            'services': services,
            'listing_mode': listing_mode(),
            'region': region,
            'q': q,
            'category': category,
            'sort': sort,
        },
    )


def products_list(request):
    """Browse product-kind listings (the Shop)."""
    products = (
        BookableService.objects.filter(
            is_active=True, vendor__is_active=True, listing_kind='product'
        )
        .select_related('vendor', 'category')
    )
    q = (request.GET.get('q') or '').strip()
    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(short_description__icontains=q) | Q(description__icontains=q)
        )
    return render(
        request,
        'booking_marketplace/list.html',
        {
            'services': products.order_by('-is_bestseller', 'name'),
            'listing_mode': listing_mode(),
            'is_product_shop': True,
            'seo_title': 'Shop',
        },
    )


def places_index(request):
    """Directory of destinations (editorial), filterable by type."""
    from plugins.installed.booking_marketplace.models import PLACE_TYPES

    places = Place.objects.filter(is_active=True)
    place_type = (request.GET.get('type') or '').strip()
    if place_type:
        places = places.filter(place_type=place_type)
    # Only offer filter pills for types that actually have places.
    used = set(
        Place.objects.filter(is_active=True)
        .exclude(place_type='')
        .values_list('place_type', flat=True)
    )
    type_filters = [{'key': k, 'label': v} for k, v in PLACE_TYPES if k in used]
    return render(
        request,
        'booking_marketplace/places/index.html',
        {
            'places': places,
            'type_filters': type_filters,
            'selected_type': place_type,
            'seo_title': 'Explore places',
        },
    )


def place_detail(request, slug):
    place = get_object_or_404(Place, slug=slug, is_active=True)
    services = (
        BookableService.objects.filter(is_active=True, vendor__is_active=True)
        .filter(Q(location__iexact=place.name) | Q(region=place.region))
        .select_related('vendor')
        .distinct()[:12]
    )
    return render(
        request,
        'booking_marketplace/places/detail.html',
        {
            'place': place,
            'services': services,
            'listing_mode': listing_mode(),
            'seo_title': place.name,
        },
    )


def _region_label(key):
    """Human label for a region key — configured label if set, else title-cased."""
    return dict(REGIONS).get(key) or key.replace('-', ' ').replace('_', ' ').title()


def regions_index(request):
    """Directory of regions with listing counts + a cover image.

    Regions are derived from live data (distinct non-empty `region` values), so
    the browse works with or without a configured `BOOKING_REGIONS` list."""
    counts = dict(
        BookableService.objects.filter(is_active=True, vendor__is_active=True)
        .exclude(region='')
        .values_list('region')
        .annotate(n=Count('id'))
        .values_list('region', 'n')
    )
    # Configured order first, then any other regions present in the data.
    keys = [k for k, _ in REGIONS if k in counts] + [
        k for k in counts if k not in dict(REGIONS)
    ]
    regions = []
    for key in keys:
        cover = (
            BookableService.objects.filter(region=key, is_active=True, vendor__is_active=True)
            .exclude(image='')
            .first()
        )
        regions.append({
            'key': key,
            'label': _region_label(key),
            'count': counts.get(key, 0),
            'image': cover.image.url if cover and cover.image else None,
        })
    return render(
        request,
        'booking_marketplace/regions/index.html',
        {'regions': regions, 'seo_title': 'Explore by region'},
    )


def region_detail(request, region):
    services = (
        BookableService.objects.filter(region=region, is_active=True, vendor__is_active=True)
        .select_related('vendor', 'category')
    )
    # Accept a region that is either configured or present in the data.
    if region not in dict(REGIONS) and not services.exists():
        raise Http404('Unknown region')
    label = _region_label(region)
    return render(
        request,
        'booking_marketplace/regions/region.html',
        {
            'region_key': region,
            'region_label': label,
            'services': services,
            'listing_mode': listing_mode(),
            'seo_title': f'{label} experiences',
        },
    )


def service_detail(request, slug):
    service = get_object_or_404(
        BookableService.objects.select_related('vendor', 'category'),
        slug=slug,
        is_active=True,
    )
    is_listing = listing_mode()

    if request.method == 'POST':
        if is_listing:
            return _submit_enquiry(request, service)
        return _create_booking(request, service)

    ctx = {
        'service': service,
        'listing_mode': is_listing,
        'dates': [] if is_listing else available_dates(service),
        'sessions': [] if is_listing else available_sessions(service),
        'tiers': list(service.tiers.filter(is_active=True)),
        'addons': list(service.addons.filter(is_active=True)),
        'max_guests': service.max_guests_per_booking or 10,
        'reviews': list(service.reviews.all()[:20]),
        'review_summary': review_summary(service),
        'can_review': can_review(service, request.user),
        'similar': _similar_services(service),
        'has_map': service.latitude is not None and service.longitude is not None,
    }
    return render(request, 'booking_marketplace/detail.html', ctx)


def _similar_services(service, limit=4):
    """Other active experiences for the 'Similar experiences' rail — same region
    first, topped up with bestsellers, excluding the current one."""
    base = BookableService.objects.filter(
        is_active=True, vendor__is_active=True, listing_kind=service.listing_kind
    ).exclude(pk=service.pk).select_related('vendor')
    picks = list(base.filter(region=service.region).order_by('-is_bestseller', '-rating')[:limit]) if service.region else []
    if len(picks) < limit:
        seen = {s.pk for s in picks}
        for s in base.order_by('-is_bestseller', '-rating', '-review_count'):
            if s.pk not in seen:
                picks.append(s)
                if len(picks) >= limit:
                    break
    return picks[:limit]


def post_review(request, slug):
    service = get_object_or_404(BookableService, slug=slug, is_active=True)
    if request.method == 'POST':
        try:
            create_review(
                service,
                user=request.user,
                rating=(request.POST.get('rating') or '').strip(),
                title=(request.POST.get('title') or '').strip(),
                body=(request.POST.get('body') or '').strip(),
            )
            messages.success(request, 'Thanks for your review!')
        except BookingError as e:
            messages.error(request, str(e))
    return redirect(_detail_url(service))


def _parse_selection(request):
    """Pull tier_<id>=qty and addon_<id>=qty out of POST into two dicts."""
    tiers, addons = {}, {}
    for key, val in request.POST.items():
        if key.startswith('tier_'):
            tiers[key[5:]] = val
        elif key.startswith('addon_'):
            addons[key[6:]] = val
    return tiers, addons


def _create_booking(request, service):
    tiers, addons = _parse_selection(request)
    try:
        booking = create_booking(
            service,
            booking_date=(request.POST.get('booking_date') or '').strip(),
            guests=(request.POST.get('guests') or '1').strip(),
            name=(request.POST.get('name') or '').strip(),
            email=(request.POST.get('email') or '').strip(),
            phone=(request.POST.get('phone') or '').strip(),
            notes=(request.POST.get('notes') or '').strip(),
            time=(request.POST.get('time_slot') or '').strip(),
            tiers=tiers,
            addons=addons,
            user=request.user,
        )
    except BookingError as e:
        messages.error(request, str(e))
        return redirect(_detail_url(service))

    messages.success(
        request,
        f'Booked {service.name} for {booking.guests} on '
        f'{booking.booking_date:%a %d %b}. {service.vendor.name} will confirm shortly.',
    )
    return redirect(_detail_url(service))


def _submit_enquiry(request, service):
    tiers, addons = _parse_selection(request)
    try:
        submit_enquiry(
            service,
            name=(request.POST.get('name') or '').strip(),
            email=(request.POST.get('email') or '').strip(),
            phone=(request.POST.get('phone') or '').strip(),
            preferred_date=(request.POST.get('preferred_date') or '').strip(),
            guests=(request.POST.get('guests') or '').strip(),
            message=(request.POST.get('message') or '').strip(),
            time=(request.POST.get('time_slot') or '').strip(),
            tiers=tiers,
            addons=addons,
            user=request.user,
        )
    except BookingError as e:
        messages.error(request, str(e))
        return redirect(_detail_url(service))

    messages.success(
        request,
        f'Thanks — your enquiry about {service.name} is in. '
        f'{service.vendor.name} will be in touch shortly.',
    )
    return redirect(_detail_url(service))


def _detail_url(service) -> str:
    return f'/bookings/{service.slug}/'
