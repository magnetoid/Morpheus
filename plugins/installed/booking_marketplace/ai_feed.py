"""AI_FEED_ITEMS filter subscriber.

``/ai/products.json`` is the feed AI shopping crawlers read, and seo builds
it from catalog ``Product`` rows. This store's inventory is not catalog
Products — it is ``BookableService`` (experiences) and ``Property`` (stays)
— so the feed truthfully reported an empty shop to every AI crawler while
142 experiences and 100 stays sat live on the site.

Folds them in over `core.hooks` so seo never imports this plugin (CLAUDE.md:
cross-plugin flows go through the bus only). Registered in `plugin.py:ready()`
with `plugin='booking_marketplace'` ownership, so the bus skips it for free
while this plugin is disabled — same arrangement as `sitemap.py`.

Entries are bare schema.org objects; seo assigns the ListItem wrapper and
`position`.
"""

from __future__ import annotations

from urllib.parse import urljoin

from core.utils.site import absolutize, site_base_url


def _money(value) -> tuple[str, str] | None:
    """(amount, currency) for a djmoney field, or None when unpriced."""
    try:
        if value is None or value.amount is None or value.amount <= 0:
            return None
        return f'{value.amount:.2f}', str(value.currency)
    except (AttributeError, TypeError):
        return None


def _rating(svc) -> dict | None:
    """schema.org aggregateRating over the experience's verified reviews only.

    Never from the denormalised rating/review_count columns, which count
    seeded rows too (services.verified_reviews) — reading them published
    40,733 reviews to every AI crawler while the database held 559, all
    seeded. A stay gets none: Property has no reviews at all (its columns
    are seeded/editorial), and the hotel page already omits it
    (seo_jsonld._hotel_node).
    """
    from plugins.installed.booking_marketplace.services import verified_rating

    count, avg = verified_rating(svc)
    if not count:
        return None
    return {'@type': 'AggregateRating', 'ratingValue': f'{avg:.1f}', 'reviewCount': count}


def _common(obj, url: str) -> dict:
    node = {
        'name': obj.name,
        'url': url,
        'description': (obj.short_description or obj.description or '').strip()[:500],
    }
    if getattr(obj, 'image', None):
        node['image'] = absolutize(obj.image.url)
    return node


def _service_item(svc, base: str) -> dict:
    url = urljoin(base, f'/bookings/{svc.slug}/')
    node = {'@type': 'Product', **_common(svc, url)}
    node['brand'] = {'@type': 'Organization', 'name': svc.vendor.name}
    rating = _rating(svc)
    if rating:
        node['aggregateRating'] = rating
    priced = _money(svc.price)
    if priced:
        amount, currency = priced
        node['offers'] = {
            '@type': 'Offer',
            'price': amount,
            'priceCurrency': currency,
            'availability': 'https://schema.org/InStock',
            'url': url,
        }
    return node


def _property_item(prop, base: str) -> dict:
    url = urljoin(base, f'/hotels/{prop.slug}/')
    node = {'@type': 'Hotel', **_common(prop, url)}
    if prop.star_rating:
        node['starRating'] = {'@type': 'Rating', 'ratingValue': prop.star_rating}
    address = {'@type': 'PostalAddress', 'addressCountry': 'ME'}
    if prop.address:
        address['streetAddress'] = prop.address
    if prop.location:
        address['addressLocality'] = prop.location
    node['address'] = address
    if prop.latitude is not None and prop.longitude is not None:
        node['geo'] = {
            '@type': 'GeoCoordinates',
            'latitude': str(prop.latitude),
            'longitude': str(prop.longitude),
        }
    priced = _money(prop.price_from)
    if priced:
        amount, currency = priced
        # `price_from` is a nightly floor, so it is an offer *range* opener —
        # schema.org's lowPrice, not a fixed price we would be quoting.
        node['priceRange'] = f'from {amount} {currency}'
        node['makesOffer'] = {
            '@type': 'Offer',
            'priceSpecification': {
                '@type': 'PriceSpecification',
                'minPrice': amount,
                'priceCurrency': currency,
            },
            'url': url,
        }
    return node


def contribute_ai_feed_items(value, **kwargs):
    """AI_FEED_ITEMS subscriber — appends live experiences and stays."""
    from plugins.installed.booking_marketplace.models import BookableService, Property
    from plugins.installed.booking_marketplace.services import with_verified_rating

    base = site_base_url()
    items = list(value or [])
    items.extend(
        _service_item(svc, base)
        for svc in with_verified_rating(
            BookableService.objects.filter(is_active=True, vendor__is_active=True)
        ).select_related('vendor')
    )
    items.extend(
        _property_item(prop, base)
        for prop in Property.objects.filter(is_active=True, vendor__is_active=True).select_related(
            'vendor'
        )
    )
    return items
