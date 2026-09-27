"""Booking marketplace — storefront views (only wired while the plugin is on).

Two operating modes (parity with the reference montenegro-experience-hub):
- MARKETPLACE mode (default): prices shown, the detail page shows a date + guests
  booking form → create_booking (server-derived totals + capacity check).
- LISTING/ENQUIRY mode (opt-in via BOOKING_ENQUIRY_MODE=1): prices hidden, the
  detail page shows a "Contact for price" enquiry form → submit_enquiry.
"""

from __future__ import annotations

import calendar

from django.conf import settings
from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from plugins.installed.booking_marketplace import seo_jsonld
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
    """Enquiry mode (opt-in; no prices/payments). Defaults to False (marketplace mode)."""
    return getattr(settings, 'BOOKING_LISTING_MODE', False)


def payments_ready() -> bool:
    """True once a payment step gates confirmation (see settings.BOOKING_PAYMENTS_READY)."""
    return getattr(settings, 'BOOKING_PAYMENTS_READY', False)


def takes_enquiry_only() -> bool:
    """Whether a submit must capture an ENQUIRY rather than confirm a booking.

    Two independent reasons, and conflating them is what shipped free confirmed
    bookings to production: `listing_mode` hides prices (a merchandising choice),
    while `payments_ready` says money can actually be taken (a safety one). A
    confirmed booking holds real inventory, so it must never be created while
    nothing charges for it — regardless of whether prices happen to be visible.
    """
    return listing_mode() or not payments_ready()


def services_list(request):
    """Browse bookable experiences across all hosts."""
    services = BookableService.objects.filter(
        is_active=True, vendor__is_active=True, listing_kind='experience'
    ).select_related('vendor', 'category')
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
    seo_title = (
        _('%(category)s experiences in Montenegro') % {'category': category}
        if category
        else _('Experiences in Montenegro — book with local hosts')
    )
    seo_description = (
        _(
            'Book %(category)s experiences in Montenegro with trusted local hosts '
            '— instant confirmation, free cancellation on most tours.'
        )
        % {'category': category}
        if category
        else _('Tours, activities and rentals from trusted local hosts across the Adriatic.')
    )
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
            'seo_title': seo_title,
            'seo_description': seo_description,
            'list_jsonld': seo_jsonld.experiences_index_jsonld(services, request=request),
        },
    )


def products_list(request):
    """Browse product-kind listings (the Shop)."""
    products = BookableService.objects.filter(
        is_active=True, vendor__is_active=True, listing_kind='product'
    ).select_related('vendor', 'category')
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
            'seo_title': 'Shop Montenegro — local goods',
            'seo_description': (
                'Locally made Montenegrin products from trusted vendors — shipped '
                'or ready for pickup across the Adriatic coast.'
            ),
        },
    )


def places_index(request):
    """Directory of Montenegro destinations (editorial), grouped by region."""
    from plugins.installed.booking_marketplace.models import PLACE_TYPES

    place_type = (request.GET.get('type') or '').strip()
    qs = Place.objects.filter(is_active=True)
    if place_type:
        qs = qs.filter(place_type=place_type)
    places = list(qs)

    # Group by region, in canonical REGIONS order (blank/unknown regions last).
    region_labels = dict(REGIONS)
    by_region: dict[str, list] = {}
    for p in places:
        by_region.setdefault(p.region, []).append(p)
    region_groups = [
        {'key': key, 'label': label, 'places': by_region[key]}
        for key, label in REGIONS
        if key in by_region
    ]
    for key, group_places in by_region.items():
        if key not in region_labels:
            region_groups.append(
                {'key': key, 'label': key or 'Elsewhere in Montenegro', 'places': group_places}
            )

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
            'region_groups': region_groups,
            'type_filters': type_filters,
            'selected_type': place_type,
            'seo_title': _('Explore Montenegro'),
            'seo_description': _(
                'Destination guides to the best places to visit in Montenegro — the Bay of '
                'Kotor, the Budva Riviera, Durmitor, Lake Skadar and the southern Adriatic '
                'coast.'
            ),
            'places_jsonld': seo_jsonld.places_index_jsonld(places, request=request),
        },
    )


def _place_meta_description(place) -> str:
    """A 150–160 char meta description: the curated summary, topped up from the
    overview when the summary alone is too short for a strong SERP snippet."""
    desc = (place.summary or '').strip()
    if len(desc) < 130 and (place.overview or '').strip():
        desc = f'{desc} {place.overview.strip()}'.strip()
    return desc[:158].rstrip(' ,.;—-')


def place_detail(request, slug):
    place = get_object_or_404(Place, slug=slug, is_active=True)
    services = (
        BookableService.objects.filter(is_active=True, vendor__is_active=True)
        .filter(Q(location__iexact=place.name) | Q(region=place.region))
        .select_related('vendor')
        .distinct()[:12]
    )
    region_siblings = (
        list(Place.objects.filter(is_active=True, region=place.region).exclude(pk=place.pk)[:6])
        if place.region
        else []
    )
    from plugins.installed.booking_marketplace.place_content import good_for_cards

    return render(
        request,
        'booking_marketplace/places/detail.html',
        {
            'place': place,
            'services': services,
            'region_siblings': region_siblings,
            'place_events': list(place.events.filter(is_active=True)[:6]),
            'good_for_cards': good_for_cards(place.good_for),
            'listing_mode': listing_mode(),
            # Per-place SEO/AEO: feeds the shared seo_meta fallbacks + og:image.
            'seo_title': f'{place.name} Travel Guide, Tours & Hotels',
            'seo_description': _place_meta_description(place),
            'seo_image': place.image.url if place.image else '',
            'seo_og_type': 'article',
            'place_jsonld': seo_jsonld.place_jsonld(place, request=request),
        },
    )


def regions_index(request):
    """Directory of Montenegro regions with experience counts + a cover image."""
    counts = dict(
        BookableService.objects.filter(is_active=True, vendor__is_active=True)
        .exclude(region='')
        .values_list('region')
        .annotate(n=Count('id'))
        .values_list('region', 'n')
    )
    regions = []
    for key, label in REGIONS:
        cover = (
            BookableService.objects.filter(region=key, is_active=True, vendor__is_active=True)
            .exclude(image='')
            .first()
        )
        regions.append(
            {
                'key': key,
                'label': label,
                'count': counts.get(key, 0),
                'image': cover.image.url if cover and cover.image else None,
            }
        )
    return render(
        request,
        'booking_marketplace/regions/index.html',
        {
            'regions': regions,
            'seo_title': 'Explore Montenegro by region',
            'regions_jsonld': seo_jsonld.regions_index_jsonld(regions, request=request),
        },
    )


def region_detail(request, region):
    labels = dict(REGIONS)
    if region not in labels:
        raise Http404('Unknown region')
    services = BookableService.objects.filter(
        region=region, is_active=True, vendor__is_active=True
    ).select_related('vendor', 'category')
    return render(
        request,
        'booking_marketplace/regions/region.html',
        {
            'region_key': region,
            'region_label': labels[region],
            'services': services,
            'listing_mode': listing_mode(),
            'seo_title': f'{labels[region]} experiences',
            'region_jsonld': seo_jsonld.region_jsonld(
                region, labels[region], services, request=request
            ),
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
        # Enquiry unless a payment step can actually charge — a confirmed booking
        # holds inventory, so it must never be free. See takes_enquiry_only().
        if takes_enquiry_only():
            return _submit_enquiry(request, service)
        return _create_booking(request, service)

    ctx = {
        'service': service,
        'listing_mode': is_listing,
        'enquiry_only': takes_enquiry_only(),
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
        # Per-page SEO/AEO: feeds the shared seo_meta fallbacks + og:image.
        'seo_object': service,
        'seo_title': f'{service.name} · {service.location or "Montenegro"}',
        'seo_description': (service.short_description or service.description)[:155],
        'seo_image': service.image.url if service.image else '',
        'seo_og_type': 'product',
        'seo_jsonld': seo_jsonld.experience_jsonld(service, request=request),
    }
    return render(request, 'booking_marketplace/detail.html', ctx)


def _similar_services(service, limit=4):
    """Other active experiences for the 'Similar experiences' rail — same region
    first, topped up with bestsellers, excluding the current one."""
    base = (
        BookableService.objects.filter(
            is_active=True, vendor__is_active=True, listing_kind=service.listing_kind
        )
        .exclude(pk=service.pk)
        .select_related('vendor')
    )
    picks = (
        list(base.filter(region=service.region).order_by('-is_bestseller', '-rating')[:limit])
        if service.region
        else []
    )
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
            # The marketplace booking form (shown whenever prices are visible)
            # posts its date as `booking_date`; the listing-mode form as
            # `preferred_date`. Either way it is the date the guest chose.
            preferred_date=(
                request.POST.get('preferred_date') or request.POST.get('booking_date') or ''
            ).strip(),
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


def events_index(request):
    """Calendar of Montenegro events, grouped by month.

    Grouped by `month` rather than by date because most editions are annual
    fixtures with no announced date yet (see the Event model docstring). Events
    with no month at all sort last under "Dates to be announced".
    """
    from plugins.installed.booking_marketplace.models import EVENT_CATEGORIES, Event

    category = (request.GET.get('category') or '').strip()
    qs = Event.objects.filter(is_active=True).select_related('place')
    if category:
        qs = qs.filter(category=category)
    events = list(qs)

    by_month: dict[int, list] = {}
    for e in events:
        by_month.setdefault(e.month, []).append(e)
    # Months 1–12 in order; the 0 ("unset") bucket always goes last.
    month_groups = [
        {'month': m, 'label': calendar.month_name[m], 'events': by_month[m]}
        for m in sorted(k for k in by_month if k)
    ]
    if 0 in by_month:
        month_groups.append(
            {'month': 0, 'label': _('Dates to be announced'), 'events': by_month[0]}
        )

    used = set(
        Event.objects.filter(is_active=True).exclude(category='').values_list('category', flat=True)
    )
    return render(
        request,
        'booking_marketplace/events/index.html',
        {
            'events': events,
            'month_groups': month_groups,
            'category_filters': [{'key': k, 'label': v} for k, v in EVENT_CATEGORIES if k in used],
            'selected_category': category,
            'seo_title': _('Montenegro Events Calendar'),
            'seo_description': _(
                "What's on in Montenegro through the year — Kotor Carnival, the Mimosa "
                'Festival, Boka Night, summer theatre in Budva, Lake Fest and the winter '
                'ski season.'
            ),
            'events_jsonld': seo_jsonld.events_index_jsonld(events, request=request),
        },
    )


def event_detail(request, slug):
    from plugins.installed.booking_marketplace.models import Event

    event = get_object_or_404(Event.objects.select_related('place'), slug=slug, is_active=True)
    # What else is on in the same month, so a visitor planning a trip sees the
    # whole window rather than one fixture.
    same_month = (
        list(
            Event.objects.filter(is_active=True, month=event.month)
            .exclude(pk=event.pk)
            .select_related('place')[:6]
        )
        if event.month
        else []
    )
    services = (
        BookableService.objects.filter(is_active=True, vendor__is_active=True)
        .filter(
            Q(region=event.region) | Q(location__iexact=(event.place.name if event.place else ''))
        )
        .select_related('vendor')
        .distinct()[:6]
        if (event.region or event.place)
        else []
    )
    return render(
        request,
        'booking_marketplace/events/detail.html',
        {
            'event': event,
            'same_month': same_month,
            'services': services,
            'listing_mode': listing_mode(),
            'seo_title': f'{event.name} — {event.when_display or "Montenegro"}'.strip(' —'),
            'seo_description': (
                event.summary or f'{event.name} in Montenegro. Dates, location and what to expect.'
            )[:300],
            'seo_image': event.image.url if event.image else '',
            'seo_og_type': 'article',
            'event_jsonld': seo_jsonld.event_jsonld(event, request=request),
        },
    )
