"""A region's landing pages: the region, and the region × category pages below it (v0.161.0).

"Kotor boat tours" had no page: `/bookings/?region=kotor&category=boat-tours` lists them,
but a filter address canonicalises to `/bookings/`, so it is never the page a search
engine keeps. `/regions/<key>/<category>/` is that page: the live experiences in the
region whose category sits in the category's subtree (catalog/category_tree.py, the
rule the shop's filters use), introduced by the region's own geography (country.py)
and the category's own description. The region page links each such page that has
experiences, with its count, and the sitemap lists exactly those.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from django.utils.text import capfirst

from plugins.installed.booking_marketplace import country

# How the experiences are ordered where no search ranks them: as /bookings/ recommends.
RECOMMENDED = ('-is_bestseller', '-rating', '-review_count', 'name')


def live_experiences():
    from plugins.installed.booking_marketplace.models import BookableService

    return BookableService.objects.filter(
        is_active=True, vendor__is_active=True, listing_kind='experience'
    )


def experiences(region: str, category):
    """The live experiences in `region` whose category is in `category`'s subtree."""
    from plugins.installed.catalog.category_tree import subtree_ids

    return (
        live_experiences()
        .filter(region=region, category_id__in=subtree_ids([category]))
        .select_related('vendor', 'category')
        .order_by(*RECOMMENDED)
    )


def category_counts() -> dict[str, list[tuple[object, int]]]:
    """{region: [(category, live experiences), …]}: each landing page that has something on it.

    An experience counts for its own category and for each active category above it,
    up to the first switched-off one: that is the subtree rule read from below, so a
    count here is what the landing page lists. In the shop's category order.
    """
    from plugins.installed.catalog.category_tree import display_tree
    from plugins.installed.catalog.models import Category

    active = {c.pk: c for c in Category.objects.filter(is_active=True)}
    known = {key for key, _label in country.regions()}
    counts: dict[str, Counter] = defaultdict(Counter)
    rows = live_experiences().exclude(region='').exclude(category__isnull=True)
    for region, category_id in rows.values_list('region', 'category_id'):
        if region not in known:
            continue
        pk = category_id
        while pk in active:
            counts[region][pk] += 1
            pk = active[pk].parent_id
    order = {c.pk: i for i, c in enumerate(display_tree())}
    out = {}
    for region, counter in counts.items():
        ranked = sorted(
            counter, key=lambda pk: (order.get(pk, len(order)), active[pk].name.lower())
        )
        out[region] = [(active[pk], counter[pk]) for pk in ranked]
    return out


def region_intro(region: str) -> str:
    """The region's geography as a sentence ('' for "elsewhere", which names only the country)."""
    here = country.current()
    context = here.region_context.get(region)
    if not context or str(context) == str(here.name):
        return ''
    return f'{capfirst(str(context))}.'


def hotels(region: str, limit: int = 8) -> list:
    from plugins.installed.booking_marketplace.models import Property

    return list(
        Property.objects.filter(region=region, is_active=True, vendor__is_active=True).order_by(
            'name'
        )[:limit]
    )


def places(region: str, limit: int = 8) -> list:
    from plugins.installed.booking_marketplace.models import Place

    return list(Place.objects.filter(region=region, is_active=True)[:limit])


def upcoming_events(region: str, limit: int = 6) -> list:
    """Events in the region, or at a place in it, that are still to come.

    An annual event always comes round again, and one with no date yet is still to
    be announced; a one-off whose last day has passed is over. Soonest month first,
    counted from this month; an event with no month goes last.
    """
    from django.db.models import Q

    from core.utils.site import store_today
    from plugins.installed.booking_marketplace.models import Event

    today = store_today()
    rows = Event.objects.filter(Q(region=region) | Q(place__region=region), is_active=True)
    rows = rows.select_related('place').distinct()
    upcoming = [e for e in rows if not e.has_ended(today)]

    def soon(e):
        return ((e.month - today.month) % 12 if e.month else 12, e.sort_order, e.name)

    return sorted(upcoming, key=soon)[:limit]
