"""Montenegro-local schema.org JSON-LD builders for Places + Experiences (SEO/AEO).

Returns JSON strings the storefront emits inside `{% block extra_head %}`. Kept
out of the shared `seo` plugin on purpose — this is Montenegro Place/
TouristDestination and experience Product markup, not generic store schema. All
money/identity logic elsewhere; this module is pure serialization.
"""

from __future__ import annotations

import json


def _abs(request, path: str) -> str:
    if not path:
        return ''
    try:
        return request.build_absolute_uri(path)
    except Exception:  # noqa: BLE001 — never let schema building break a page
        return path


def _place_url(request, place) -> str:
    return _abs(request, f'/places/{place.slug}/')


def _destination_node(place, *, request) -> dict:
    node = {
        '@type': 'TouristDestination',
        '@id': _place_url(request, place) + '#destination',
        'name': place.name,
        'description': place.summary or (place.overview or '')[:300] or place.name,
        'url': _place_url(request, place),
    }
    if place.image:
        node['image'] = _abs(request, place.image.url)
    if place.latitude is not None and place.longitude is not None:
        node['geo'] = {
            '@type': 'GeoCoordinates',
            'latitude': str(place.latitude),
            'longitude': str(place.longitude),
        }
    address = {'@type': 'PostalAddress', 'addressCountry': 'ME'}
    region_label = place.get_region_display() if place.region else ''
    if region_label:
        address['addressRegion'] = region_label
    node['address'] = address
    node['containedInPlace'] = {'@type': 'Country', 'name': 'Montenegro'}
    # sameAs: authoritative outbound references (UNESCO, tourism board,
    # Wikipedia) strengthen entity disambiguation for AEO / knowledge graphs.
    same_as = [
        link['url']
        for link in (getattr(place, 'external_links', None) or [])
        if isinstance(link, dict) and link.get('url')
    ]
    if same_as:
        node['sameAs'] = same_as
    return node


def _faq_node(obj) -> dict | None:
    """FAQPage from an object's ``.faqs`` [{q, a}] list (Place or BookableService)."""
    faqs = [f for f in (getattr(obj, 'faqs', None) or []) if f.get('q') and f.get('a')]
    if not faqs:
        return None
    return {
        '@type': 'FAQPage',
        'mainEntity': [
            {
                '@type': 'Question',
                'name': f['q'],
                'acceptedAnswer': {'@type': 'Answer', 'text': f['a']},
            }
            for f in faqs
        ],
    }


def _breadcrumb(request, trail) -> dict:
    """trail: list of (name, path) from Home to the current page."""
    return {
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': i + 1, 'name': name, 'item': _abs(request, path)}
            for i, (name, path) in enumerate(trail)
        ],
    }


# Same escaping schema.org/JSON-LD hardening applies in the shared seo plugin
# (plugins/installed/seo/services/_helpers.py:_jsonld_dump) — neutralises the
# characters that can break out of a <script type="application/ld+json">
# element. Reimplemented locally (this module deliberately stays out of the
# seo plugin, see module docstring) rather than importing it: free-text
# fields (place name/overview, experience name/description/review body) are
# merchant/guest/editorial input and json.dumps alone passes `</script>`
# through unescaped.
_JSONLD_ESCAPES = {
    0x3C: '\\u003C',  # <
    0x3E: '\\u003E',  # >
    0x26: '\\u0026',  # &
    0x2028: '\\u2028',  # line separator (invalid raw in a <script> body)
    0x2029: '\\u2029',  # paragraph separator
}


def _dump(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False).translate(_JSONLD_ESCAPES)


def place_jsonld(place, *, request) -> str:
    """@graph: TouristDestination (+ geo/address), optional FAQPage, BreadcrumbList."""
    graph = [_destination_node(place, request=request)]
    faq = _faq_node(place)
    if faq:
        graph.append(faq)
    graph.append(
        _breadcrumb(
            request,
            [
                ('Home', '/'),
                ('Places', '/places/'),
                (place.name, f'/places/{place.slug}/'),
            ],
        )
    )
    return _dump({'@context': 'https://schema.org', '@graph': graph})


def _service_url(request, service) -> str:
    return _abs(request, f'/bookings/{service.slug}/')


def _product_node(service, *, request) -> dict:
    url = _service_url(request, service)
    node = {
        '@type': 'Product',
        '@id': url + '#product',
        'name': service.name,
        'description': service.short_description or service.description[:300] or service.name,
        'url': url,
    }
    if service.image:
        node['image'] = _abs(request, service.image.url)
    node['brand'] = {'@type': 'Organization', 'name': service.vendor.name}
    node['offers'] = {
        '@type': 'Offer',
        'price': str(service.price.amount),
        'priceCurrency': 'EUR',
        'availability': 'https://schema.org/InStock',
        'url': url,
    }
    if service.review_count:
        node['aggregateRating'] = {
            '@type': 'AggregateRating',
            'ratingValue': str(service.rating),
            'reviewCount': service.review_count,
        }
        # ServiceReview's default ordering is -created_at, so this is
        # already "up to 5, newest first".
        reviews = list(service.reviews.all()[:5])
        if reviews:
            node['review'] = [
                {
                    '@type': 'Review',
                    'author': {'@type': 'Person', 'name': r.author_name or 'Guest'},
                    'reviewRating': {'@type': 'Rating', 'ratingValue': r.rating},
                    'reviewBody': r.body,
                }
                for r in reviews
            ]
    return node


def experience_jsonld(service, *, request) -> str:
    """@graph: Product (+ Offer, optional AggregateRating/Review), optional FAQPage, BreadcrumbList.

    The on-page "Guest questions" accordion (service.faqs) is mirrored into a
    FAQPage node so answer engines (ChatGPT/Perplexity/Google AI) can quote it.
    """
    graph = [_product_node(service, request=request)]
    faq = _faq_node(service)
    if faq:
        graph.append(faq)
    graph.append(
        _breadcrumb(
            request,
            [
                ('Home', '/'),
                ('Experiences', '/bookings/'),
                (service.name, f'/bookings/{service.slug}/'),
            ],
        )
    )
    return _dump({'@context': 'https://schema.org', '@graph': graph})


def places_index_jsonld(places, *, request) -> str:
    """@graph: CollectionPage + ItemList of places + BreadcrumbList."""
    items = [
        {'@type': 'ListItem', 'position': i + 1, 'name': p.name, 'url': _place_url(request, p)}
        for i, p in enumerate(places)
    ]
    graph = [
        {
            '@type': 'CollectionPage',
            'name': 'Places in Montenegro',
            'url': _abs(request, '/places/'),
        },
        {'@type': 'ItemList', 'itemListElement': items},
        _breadcrumb(request, [('Home', '/'), ('Places', '/places/')]),
    ]
    return _dump({'@context': 'https://schema.org', '@graph': graph})


# --------------------------------------------------------------------------- #
# Accommodation (Property) — LodgingBusiness/Hotel markup.                     #
# --------------------------------------------------------------------------- #


def _stay_url(request, prop) -> str:
    return _abs(request, f'/hotels/{prop.slug}/')


def _hotel_node(prop, *, request, with_prices=True) -> dict:
    """Hotel (a LodgingBusiness). Only emits fields that are also visible on the
    page: starRating is the hotel class (shown as ★), amenities/check-in are
    rendered; guest aggregateRating is deliberately omitted (not shown on-page,
    which Google's rich-results policy requires). Prices are gated by
    ``with_prices`` so listing mode ("Contact for price") stays consistent.
    """
    from plugins.installed.booking_marketplace.models import AMENITY_LABELS

    url = _stay_url(request, prop)
    node = {
        '@type': 'Hotel',
        '@id': url + '#hotel',
        'name': prop.name,
        'description': prop.short_description or (prop.description or '')[:300] or prop.name,
        'url': url,
    }
    if prop.image:
        node['image'] = _abs(request, prop.image.url)
    address = {'@type': 'PostalAddress', 'addressCountry': 'ME'}
    if prop.address:
        address['streetAddress'] = prop.address
    if prop.location:
        address['addressLocality'] = prop.location
    region_label = prop.get_region_display() if prop.region else ''
    if region_label:
        address['addressRegion'] = region_label
    node['address'] = address
    if prop.latitude is not None and prop.longitude is not None:
        node['geo'] = {
            '@type': 'GeoCoordinates',
            'latitude': str(prop.latitude),
            'longitude': str(prop.longitude),
        }
    if prop.star_rating:
        node['starRating'] = {'@type': 'Rating', 'ratingValue': prop.star_rating, 'bestRating': 5}
    amenities = [
        AMENITY_LABELS.get(s, (s.replace('_', ' ').title(),))[0] for s in (prop.amenities or [])
    ]
    if amenities:
        node['amenityFeature'] = [
            {'@type': 'LocationFeatureSpecification', 'name': a, 'value': True} for a in amenities
        ]
    if prop.check_in_time:
        node['checkinTime'] = prop.check_in_time.strftime('%H:%M')
    if prop.check_out_time:
        node['checkoutTime'] = prop.check_out_time.strftime('%H:%M')
    if with_prices:
        if prop.price_from and prop.price_from.amount:
            node['priceRange'] = f'From €{int(prop.price_from.amount)}'
        offers = [
            {
                '@type': 'Offer',
                'name': r.name,
                'price': str(r.base_rate.amount),
                'priceCurrency': 'EUR',
                'availability': 'https://schema.org/InStock',
                'url': url,
            }
            for r in prop.room_types.all()
            if r.is_active and r.base_rate and r.base_rate.amount
        ]
        if offers:
            node['makesOffer'] = offers
    return node


def property_jsonld(prop, *, request, with_prices=True) -> str:
    """@graph: Hotel (+ geo, address, amenities, star rating, room Offers),
    BreadcrumbList. The hotels' inventory previously emitted no structured data
    at all — this is the single biggest tourism-SEO gap closed."""
    graph = [
        _hotel_node(prop, request=request, with_prices=with_prices),
        _breadcrumb(
            request,
            [('Home', '/'), ('Hotels', '/hotels/'), (prop.name, f'/hotels/{prop.slug}/')],
        ),
    ]
    return _dump({'@context': 'https://schema.org', '@graph': graph})


# --------------------------------------------------------------------------- #
# Listing pages — CollectionPage + ItemList + BreadcrumbList (helps engines    #
# understand "experiences in Montenegro" / "hotels" as a browseable set).      #
# --------------------------------------------------------------------------- #


def _collection_jsonld(*, request, name, path, rows, trail) -> str:
    """@graph: CollectionPage + ItemList(rows: [(name, path)]) + BreadcrumbList(trail)."""
    items = [
        {'@type': 'ListItem', 'position': i + 1, 'name': n, 'url': _abs(request, p)}
        for i, (n, p) in enumerate(rows)
    ]
    graph = [
        {'@type': 'CollectionPage', 'name': name, 'url': _abs(request, path)},
        {'@type': 'ItemList', 'itemListElement': items},
        _breadcrumb(request, trail),
    ]
    return _dump({'@context': 'https://schema.org', '@graph': graph})


def experiences_index_jsonld(services, *, request) -> str:
    return _collection_jsonld(
        request=request,
        name='Experiences in Montenegro',
        path='/bookings/',
        rows=[(s.name, f'/bookings/{s.slug}/') for s in services],
        trail=[('Home', '/'), ('Experiences', '/bookings/')],
    )


def stays_index_jsonld(properties, *, request) -> str:
    return _collection_jsonld(
        request=request,
        name='Hotels & stays in Montenegro',
        path='/hotels/',
        rows=[(p.name, f'/hotels/{p.slug}/') for p in properties],
        trail=[('Home', '/'), ('Hotels', '/hotels/')],
    )


def region_jsonld(region_key, region_label, services, *, request) -> str:
    path = f'/regions/{region_key}/'
    return _collection_jsonld(
        request=request,
        name=f'{region_label} — experiences in Montenegro',
        path=path,
        rows=[(s.name, f'/bookings/{s.slug}/') for s in services],
        trail=[('Home', '/'), ('Regions', '/regions/'), (region_label, path)],
    )


def regions_index_jsonld(regions, *, request) -> str:
    return _collection_jsonld(
        request=request,
        name='Montenegro by region',
        path='/regions/',
        rows=[(r['label'], f'/regions/{r["key"]}/') for r in regions],
        trail=[('Home', '/'), ('Regions', '/regions/')],
    )


def _event_url(request, event) -> str:
    return _abs(request, f'/events/{event.slug}/')


def event_jsonld(event, *, request) -> str:
    """schema.org/Event for a single event page.

    The Event node is emitted **only when a concrete `start_date` exists.**
    `startDate` is required by schema.org and by Google's Event rich result, and
    most of these are annual fixtures whose next edition is announced weeks
    ahead — so the honest options are a dated node or no node, never a guessed
    date. Undated events still ship FAQ + breadcrumb markup, and the page still
    tells a human "Early February" via `when_display`.
    """
    graph = []
    if event.start_date:
        node = {
            '@type': 'Event',
            '@id': _event_url(request, event) + '#event',
            'name': event.name,
            'url': _event_url(request, event),
            'startDate': event.start_date.isoformat(),
            'eventStatus': 'https://schema.org/EventScheduled',
            'eventAttendanceMode': 'https://schema.org/OfflineEventAttendanceMode',
        }
        if event.end_date:
            node['endDate'] = event.end_date.isoformat()
        if event.summary:
            node['description'] = event.summary
        if event.image:
            node['image'] = _abs(request, event.image.url)
        if event.official_url:
            node['sameAs'] = event.official_url
        address = {'@type': 'PostalAddress', 'addressCountry': 'ME'}
        if event.place:
            address['addressLocality'] = event.place.name
        node['location'] = {
            '@type': 'Place',
            'name': event.venue or (event.place.name if event.place else 'Montenegro'),
            'address': address,
        }
        graph.append(node)

    faq = _faq_node(event)
    if faq:
        graph.append(faq)
    graph.append(
        _breadcrumb(
            request,
            [('Home', '/'), ('Events', '/events/'), (event.name, f'/events/{event.slug}/')],
        )
    )
    return _dump({'@context': 'https://schema.org', '@graph': graph})


def events_index_jsonld(events, *, request) -> str:
    """ItemList for the events calendar."""
    return _collection_jsonld(
        request=request,
        name='Montenegro events calendar',
        path='/events/',
        rows=[(e.name, f'/events/{e.slug}/') for e in events],
        trail=[('Home', '/'), ('Events', '/events/')],
    )
