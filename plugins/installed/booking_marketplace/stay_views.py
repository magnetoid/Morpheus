"""Storefront views for the accommodation (stays) engine."""

from __future__ import annotations

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from core.utils.pagination import paginate_or_404
from plugins.installed.booking_marketplace import seo_jsonld, stay_content, stays
from plugins.installed.booking_marketplace.models import (
    AMENITY_LABELS,
    POLICY_LABELS,
    PROPERTY_TYPES,
    REGIONS,
    Property,
    RoomType,
)
from plugins.installed.booking_marketplace.services import BookingError
from plugins.installed.booking_marketplace.views import (
    _crumbs,
    _image_url,
    listing_mode,
    takes_enquiry_only,
)


def _planning_questions() -> list[dict]:
    """The "Planning your Montenegro stay" questions the hotels index shows.

    One list for the page AND its FAQPage node: the template used to hardcode
    the visible answers while a separate hand-written JSON-LD block published
    differently worded questions — markup that did not match the page.
    """
    return [
        {
            'q': _('Which area is best for a first visit?'),
            'a': _(
                'The Bay of Kotor combines historic towns, water access and easy day trips. '
                'Budva suits beach-focused stays, while Durmitor is the strongest choice for '
                'hiking.'
            ),
        },
        {
            'q': _('When should I book?'),
            'a': _(
                'Reserve early for July and August. The shoulder months of May, June, '
                'September and October often provide better value and fewer crowds.'
            ),
        },
        {
            'q': _('Do I need a car?'),
            'a': _(
                'Not always on the coast, but a car makes mountain, lake and rural '
                'itineraries easier. Local tours and transfers are practical alternatives.'
            ),
        },
    ]


def _amenities(slugs):
    out = []
    for s in slugs or []:
        label, icon = AMENITY_LABELS.get(s, (s.replace('_', ' ').title(), 'check'))
        out.append({'slug': s, 'label': str(label), 'icon': icon})
    return out


def _policies(policies):
    """Ordered [{key, label, value}] for a property's policies dict: canonical
    order from POLICY_LABELS, any extra key humanised, empty values skipped.
    Keeps the policies-dict shape out of the theme (mirrors _amenities)."""
    policies = policies or {}
    ordered = list(POLICY_LABELS) + [k for k in policies if k not in POLICY_LABELS]
    out = []
    for key in ordered:
        value = str(policies.get(key) or '').strip()
        if not value:
            continue
        label = POLICY_LABELS.get(key) or key.replace('_', ' ').capitalize()
        out.append({'key': key, 'label': str(label), 'value': value})
    return out


def stays_index(request):
    qs = Property.objects.filter(is_active=True, vendor__is_active=True)
    region = request.GET.get('region') or ''
    ptype = request.GET.get('type') or ''
    if region:
        qs = qs.filter(region=region)
    if ptype:
        qs = qs.filter(property_type=ptype)
    # 100 hotels on one page was a 167 KB document; a page past the end is a 404.
    page_obj = paginate_or_404(qs.order_by('name'), 48, request)
    properties = list(page_obj.object_list)
    return render(
        request,
        'booking_marketplace/stays/index.html',
        {
            'properties': properties,
            'page_obj': page_obj,
            'listing_mode': listing_mode(),
            'active_region': region,
            'active_type': ptype,
            'region_choices': REGIONS,
            'type_choices': PROPERTY_TYPES,
            'page_faqs': _planning_questions(),
            'seo_title': _('Hotels & stays in Montenegro'),
            'seo_description': _(
                'Hand-picked hotels, apartments and guesthouses across Montenegro — from the '
                'Bay of Kotor to the Adriatic coast and the northern mountains. Book your stay.'
            ),
            'breadcrumb_items': _crumbs(request, (_('Hotels'), '/hotels/')),
            'jsonld_items': seo_jsonld.listing_items(
                [(p.name, f'/hotels/{p.slug}/', _image_url(p)) for p in properties[:60]],
                request=request,
            ),
            'seo_item_count': page_obj.paginator.count,
        },
    )


def stay_detail(request, slug):
    # A deactivated host's hotels are gone from the lists and the sitemap; the
    # page must agree, not keep answering 200.
    prop = get_object_or_404(
        Property.objects.prefetch_related('room_types', 'images'),
        slug=slug,
        is_active=True,
        vendor__is_active=True,
    )
    nearby = stays.nearby_places(prop)
    return render(
        request,
        'booking_marketplace/stays/detail.html',
        {
            'property': prop,
            'room_types': prop.room_types.filter(is_active=True),
            'amenities': _amenities(prop.amenities),
            # Data-grounded per-property copy: a unique "Staying in…" intro +
            # a "Best for" profile from this hotel's own type/stars/amenities
            # (stay_content) — replaces the boilerplate that repeated on all 68.
            'best_for': stay_content.best_for(prop),
            'location_intro': stay_content.location_intro(prop, nearby),
            'nearby_places': nearby,
            'related_stays': stays.related_stays(prop),
            'policy_items': _policies(prop.policies),
            'listing_mode': listing_mode(),
            # Per-page SEO/AEO: feeds the shared seo_meta fallbacks + og:image.
            'seo_object': prop,
            'seo_title': f'{prop.name} · {prop.location or _("Montenegro")}',
            'seo_description': (prop.short_description or prop.description)[:155],
            'seo_image': prop.image.url if prop.image else '',
            'seo_og_type': 'product',
            # The Hotel node joins the head's graph through SEO_JSONLD_GRAPH
            # (booking_marketplace/seo.py), prices gated to non-listing mode.
            'breadcrumb_items': _crumbs(
                request, (_('Hotels'), '/hotels/'), (prop.name, f'/hotels/{prop.slug}/')
            ),
        },
    )


def stay_quote(request, slug):
    room_type = get_object_or_404(
        RoomType,
        pk=request.GET.get('room_type'),
        property__slug=slug,
        property__is_active=True,
        property__vendor__is_active=True,
        is_active=True,
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
    prop = get_object_or_404(Property, slug=slug, is_active=True, vendor__is_active=True)
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
