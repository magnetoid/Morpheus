"""How the travel marketplace's pages describe themselves to the platform.

Five hook answers, each replacing something that used to be hardcoded or simply
absent — every one of them visible on montenegro-experience.me:

* `SEO_RESOLVE_PAGE` — what each route IS. Unclaimed, the listings resolved as
  plain static pages (so an empty region stayed indexable and `/bookings/?q=`
  was indexable search results), and the host's own dashboard pages were
  indexable too.
* `SEO_JSONLD_GRAPH` — the entity nodes (Product, Hotel, TouristDestination,
  Event, FAQPage) join the page's ONE graph. The theme used to paste two or
  three extra `ld+json` blocks per page, including a FAQPage on the listings
  whose questions the page never showed.
* `VENDOR_LISTING_COUNTS` + `STOREFRONT_VENDOR_SECTIONS` — a host's page lists
  the host's experiences, stays and goods. All 171 host pages read "0 listings"
  and sat in the sitemap as soft 404s, because the shell counted catalog
  Products only.
* `STOREFRONT_SEARCH_PATH` — a search lands on the experiences, not on the
  empty product grid.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.booking_marketplace')

NAMESPACE = 'booking_marketplace'

# url name → listing subtype. Each is a page OF other pages: the empty-listing
# and search-results rules apply, and the head publishes its ItemList.
_LISTINGS = {
    'list': 'experiences',
    'shop': 'shop',
    'regions': 'regions',
    'region': 'region',
    'places': 'places',
    'events': 'events',
    'stays': 'stays',
}
# url name → entity subtype. One thing per page; this app adds its node.
_ENTITIES = {'detail': 'experience', 'place': 'place', 'event': 'event', 'stay_detail': 'stay'}
# A host's own back office on the storefront, and a guest's own bookings.
_PRIVATE = {
    'host_services',
    'host_new',
    'host_bookings',
    'host_enquiries',
    'host_earnings',
    'host_edit',
    'account_bookings',
}


def _route(request) -> str:
    match = getattr(request, 'resolver_match', None)
    if match is None or getattr(match, 'namespace', '') != NAMESPACE:
        return ''
    return getattr(match, 'url_name', '') or ''


def on_seo_resolve_page(value, request=None, context=None, **kwargs):
    """SEO_RESOLVE_PAGE — claim this app's routes; return `value` untouched otherwise."""
    if value is not None or request is None:
        return value
    name = _route(request)
    if not name:
        return value
    from core.seo_page import (  # noqa: PLC0415
        KIND_LISTING,
        KIND_PAGE,
        KIND_PRIVATE,
        SeoPage,
    )

    ctx = context or {}
    if name in _LISTINGS:
        kind, subtype = KIND_LISTING, _LISTINGS[name]
    elif name in _ENTITIES:
        kind, subtype = KIND_PAGE, _ENTITIES[name]
    elif name in _PRIVATE:
        kind, subtype = KIND_PRIVATE, name
    else:
        return value
    page = SeoPage(
        kind=kind,
        subtype=subtype,
        path=request.get_full_path(),
        obj=ctx.get('seo_object'),
        title=str(ctx.get('seo_title') or ''),
        description=str(ctx.get('seo_description') or ''),
        image=str(ctx.get('seo_image') or ''),
        og_type=str(ctx.get('seo_og_type') or 'website'),
        breadcrumbs=ctx.get('breadcrumb_items') or [],
        context=ctx,
    )
    if kind == KIND_PRIVATE:
        page.deny_index('host / guest account page', nofollow=True)
    return page


def on_seo_jsonld_graph(value, page=None, request=None, **kwargs):
    """SEO_JSONLD_GRAPH — add this page's entity (and its visible FAQ) to the graph."""
    try:
        name = _route(request)
        if not name or not isinstance(value, dict):
            return value
        nodes = value.setdefault('@graph', [])
        webpage = next(
            (
                n
                for n in nodes
                if isinstance(n, dict) and str(n.get('@id', '')).endswith('#webpage')
            ),
            None,
        )
        url = (webpage or {}).get('url') or request.build_absolute_uri(request.path)
        added = _entity_nodes(name, getattr(page, 'context', None) or {}, url, request)
        if not added:
            return value
        nodes.extend(added)
        primary = added[0]
        if webpage is not None and primary.get('@type') != 'FAQPage':
            webpage['mainEntity'] = {'@id': primary['@id']}
    except Exception as e:  # noqa: BLE001 — an enricher must never lose the graph
        logger.warning('booking_marketplace: JSON-LD enrichment failed: %s', e, exc_info=True)
    return value


def _entity_nodes(name: str, ctx: dict, url: str, request) -> list[dict]:
    from plugins.installed.booking_marketplace import seo_jsonld  # noqa: PLC0415

    if name == 'detail' and ctx.get('service') is not None:
        return seo_jsonld.experience_nodes(ctx['service'], url=url, request=request)
    if name == 'place' and ctx.get('place') is not None:
        return seo_jsonld.place_nodes(ctx['place'], url=url, request=request)
    if name == 'event' and ctx.get('event') is not None:
        return seo_jsonld.event_nodes(ctx['event'], url=url, request=request)
    if name == 'stay_detail' and ctx.get('property') is not None:
        return seo_jsonld.property_nodes(
            ctx['property'], url=url, request=request, with_prices=not ctx.get('listing_mode')
        )
    # A listing whose view shows planning questions (the stays index).
    faq = seo_jsonld.faq_node(ctx.get('page_faqs'), url)
    return [faq] if faq else []


# -- the host's page ---------------------------------------------------------
def _host_listings(vendor):
    from plugins.installed.booking_marketplace.models import (  # noqa: PLC0415
        BookableService,
        Property,
    )

    services = (
        BookableService.objects.filter(vendor=vendor, is_active=True)
        .select_related('vendor', 'category')
        .order_by('-is_bestseller', '-rating', 'name')
    )
    stays = Property.objects.filter(vendor=vendor, is_active=True).order_by('name')
    return services, stays


def on_vendor_listing_counts(value, **kwargs):
    """VENDOR_LISTING_COUNTS — add each host's active experiences, goods and stays."""
    from django.db.models import Count  # noqa: PLC0415

    from plugins.installed.booking_marketplace.models import (  # noqa: PLC0415
        BookableService,
        Property,
    )

    counts = dict(value or {})
    for model in (BookableService, Property):
        rows = (
            model.objects.filter(is_active=True, vendor__is_active=True)
            .values('vendor_id')
            .annotate(n=Count('pk'))
        )
        for row in rows:
            key = str(row['vendor_id'])
            counts[key] = counts.get(key, 0) + row['n']
    return counts


def on_vendor_sections(value, vendor=None, request=None, **kwargs):
    """STOREFRONT_VENDOR_SECTIONS — the host's experiences, stays and local goods."""
    from django.utils.translation import gettext  # noqa: PLC0415

    sections = list(value or [])
    if vendor is None:
        return sections
    services, stays = _host_listings(vendor)
    experiences = [s for s in services if s.listing_kind == 'experience']
    goods = [s for s in services if s.listing_kind == 'product']
    stays = list(stays)

    from core.utils.i18n import localized_path  # noqa: PLC0415

    def items(rows, path):
        return [
            {
                'name': row.name,
                'url': (
                    request.build_absolute_uri(localized_path(request, path(row)))
                    if request is not None
                    else path(row)
                ),
                'image': (row.image.url if getattr(row, 'image', None) else ''),
            }
            for row in rows[:30]
        ]

    for key, title, rows, path, order in (
        ('experiences', gettext('Experiences'), experiences, lambda r: f'/bookings/{r.slug}/', 10),
        ('stays', gettext('Stays'), stays, lambda r: f'/hotels/{r.slug}/', 20),
        ('goods', gettext('Local goods'), goods, lambda r: f'/bookings/{r.slug}/', 30),
    ):
        if not rows:
            continue
        sections.append(
            {
                'key': key,
                'title': title,
                'template': 'booking_marketplace/_vendor_section.html',
                'context': {'kind': key, 'items': rows},
                'count': len(rows),
                'order': order,
                'jsonld_items': items(rows, path),
            }
        )
    return sections


def on_search_path(value, request=None, **kwargs):
    """STOREFRONT_SEARCH_PATH — search lands where the inventory is.

    Claimed only when the experiences ARE the inventory: live experiences here
    and no active catalog product. A store that sells both keeps the catalogue's
    search, which covers its products.
    """
    from plugins.installed.booking_marketplace.models import BookableService  # noqa: PLC0415
    from plugins.installed.catalog.models import Product  # noqa: PLC0415

    if Product.objects.filter(status='active').exists():
        return value
    live = BookableService.objects.filter(
        is_active=True, vendor__is_active=True, listing_kind='experience'
    )
    return '/bookings/' if live.exists() else value
