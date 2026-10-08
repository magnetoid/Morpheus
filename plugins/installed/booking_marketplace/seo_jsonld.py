"""schema.org nodes for the Montenegro inventory: experiences, places, stays, events.

Kept out of the shared `seo` app on purpose — TouristDestination, Hotel and
experience Product markup are this vertical's knowledge, not generic store
schema. Since v0.80.0 these builders return NODES, and `seo.py` adds them to
the page's one JSON-LD graph through `SEO_JSONLD_GRAPH`.

They used to return whole `@graph` documents that the theme pasted into
`{% block extra_head %}` — so every booking page carried two or three
`<script type="application/ld+json">` blocks: the head's WebPage graph, this
one (with its own BreadcrumbList and a CollectionPage naming the URL without
its language prefix), and on the listings a hardcoded FAQPage whose questions
did not appear on the page at all. Breadcrumbs and listing ItemLists now come
from the head document (`breadcrumb_items`, `jsonld_items` in the context), and
every node is anchored to the page's canonical URL.
"""

from __future__ import annotations


def _abs(request, path: str) -> str:
    if not path:
        return ''
    try:
        return request.build_absolute_uri(path)
    except Exception:  # noqa: BLE001 — never let schema building break a page
        return path


def faq_node(pairs, url: str = '') -> dict | None:
    """FAQPage from `[{q, a}]` — only for questions the page itself shows."""
    faqs = [f for f in (pairs or []) if isinstance(f, dict) and f.get('q') and f.get('a')]
    if not faqs:
        return None
    node = {
        '@type': 'FAQPage',
        'mainEntity': [
            {
                '@type': 'Question',
                'name': str(f['q']),
                'acceptedAnswer': {'@type': 'Answer', 'text': str(f['a'])},
            }
            for f in faqs
        ],
    }
    if url:
        node['@id'] = f'{url}#faq'
    return node


def _destination_node(place, *, url: str, request=None) -> dict:
    node = {
        '@type': 'TouristDestination',
        '@id': f'{url}#destination',
        'name': place.name,
        'description': place.summary or (place.overview or '')[:300] or place.name,
        'url': url,
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


def place_nodes(place, *, url: str, request=None) -> list[dict]:
    """TouristDestination (+ geo/address), and its FAQPage when the page shows one."""
    nodes = [_destination_node(place, url=url, request=request)]
    faq = faq_node(getattr(place, 'faqs', None), url)
    if faq:
        nodes.append(faq)
    return nodes


def _product_node(service, *, url: str, request=None) -> dict:
    node = {
        '@type': 'Product',
        '@id': f'{url}#product',
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
    # Never from the denormalised rating/review_count columns: they count
    # seeded rows too (services.verified_reviews). The aggregate and the
    # Review nodes come from the same verified set.
    from plugins.installed.booking_marketplace.services import verified_rating, verified_reviews

    count, avg = verified_rating(service)
    if count:
        node['aggregateRating'] = {
            '@type': 'AggregateRating',
            'ratingValue': f'{avg:.1f}',
            'reviewCount': count,
        }
        # ServiceReview's default ordering is -created_at, so this is
        # already "up to 5, newest first".
        reviews = list(verified_reviews(service)[:5])
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


def experience_nodes(service, *, url: str, request=None) -> list[dict]:
    """Product (+ Offer, verified AggregateRating/Review) and the guest-questions FAQPage.

    The on-page "Guest questions" accordion (service.faqs) is mirrored into a
    FAQPage node so answer engines can quote it.
    """
    nodes = [_product_node(service, url=url, request=request)]
    faq = faq_node(getattr(service, 'faqs', None), url)
    if faq:
        nodes.append(faq)
    return nodes


def _hotel_node(prop, *, url: str, request=None, with_prices=True) -> dict:
    """Hotel (a LodgingBusiness). Only emits fields that are also visible on the
    page: starRating is the hotel class (shown as ★), amenities/check-in are
    rendered; guest aggregateRating is deliberately omitted (not shown on-page,
    which Google's rich-results policy requires). Prices are gated by
    ``with_prices`` so listing mode ("Contact for price") stays consistent.
    """
    from plugins.installed.booking_marketplace.models import AMENITY_LABELS

    node = {
        '@type': 'Hotel',
        '@id': f'{url}#hotel',
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


def property_nodes(prop, *, url: str, request=None, with_prices=True) -> list[dict]:
    """Hotel (+ geo, address, amenities, star rating, room Offers)."""
    return [_hotel_node(prop, url=url, request=request, with_prices=with_prices)]


def event_nodes(event, *, url: str, request=None) -> list[dict]:
    """schema.org/Event for a single event page.

    The Event node is emitted **only when a concrete `start_date` exists.**
    `startDate` is required by schema.org and by Google's Event rich result, and
    most of these are annual fixtures whose next edition is announced weeks
    ahead — so the honest options are a dated node or no node, never a guessed
    date. Undated events still ship their FAQ (and the head's breadcrumbs), and
    the page still tells a human "Early February" via `when_display`.
    """
    nodes: list[dict] = []
    if event.start_date:
        node = {
            '@type': 'Event',
            '@id': f'{url}#event',
            'name': event.name,
            'url': url,
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
        nodes.append(node)
    faq = faq_node(getattr(event, 'faqs', None), url)
    if faq:
        nodes.append(faq)
    return nodes


def listing_items(rows, *, request) -> list[dict]:
    """`jsonld_items` for a listing page: `[(name, path, image_url)]` → the head's ItemList.

    Paths are made absolute against the current request, so a Serbian page's
    ItemList names the Serbian urls.
    """
    from core.utils.i18n import localized_path

    return [
        {'name': name, 'url': _abs(request, localized_path(request, path)), 'image': image}
        for name, path, image in rows
    ]
