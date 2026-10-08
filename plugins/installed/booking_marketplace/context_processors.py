"""Global storefront navigation data for the montenegro theme header megamenus.

Category tiles and destination lists are derived live from the DB on every
render (fail-soft to empty on a fresh/mid-migration DB) so the header can
never drift from the catalog — one cheap aggregate query per render.
"""

from __future__ import annotations

# place_type → "Places" megamenu column. The nav is built live from Place
# records so a menu entry can never link to an unseeded slug. The old hardcoded
# list drifted from the seed data and 404'd 16 destinations.
_TYPE_TO_COLUMN = {
    'coastal': 'coastal',
    'mountains': 'mountains',
    'national_parks': 'mountains',
    'cities': 'cities',
    'cultural': 'cities',
    'lakes': 'landmarks',
}


def _nav_places():
    """Build the header 'Places' megamenu live from active Place records.

    Returns ``(columns, featured)``. Fails soft to empty lists if the table is
    absent (fresh DB / mid-migration) — this runs on every render and must
    never raise.
    """
    columns = {'coastal': [], 'mountains': [], 'cities': [], 'landmarks': []}
    try:
        from plugins.installed.booking_marketplace.models import Place  # noqa: PLC0415

        places = list(
            Place.objects.filter(is_active=True)
            .only('name', 'slug', 'place_type', 'is_featured', 'sort_order')
            .order_by('sort_order', 'name')
        )
    except Exception:  # noqa: BLE001 — table missing / not migrated yet
        return columns, []
    for p in places:
        columns[_TYPE_TO_COLUMN.get(p.place_type, 'landmarks')].append(
            {'name': p.name, 'slug': p.slug}
        )
    featured = [{'name': p.name, 'slug': p.slug} for p in places if p.is_featured][:6]
    if not featured:
        featured = [{'name': p.name, 'slug': p.slug} for p in places][:6]
    return columns, featured


def _nav_categories():
    """Mega-menu category tiles, derived from live categories (fail-soft)."""
    from django.utils.text import slugify
    from django.utils.translation import ngettext

    from plugins.installed.booking_marketplace.services import active_categories
    from plugins.installed.booking_marketplace.templatetags.booking_tags import (
        _CAT_ICON_DEFAULT,
        _CAT_ICONS,
        _cat_href,
    )

    tiles = []
    for c in active_categories()[:6]:
        n = c['count']
        tiles.append(
            {
                'label': c['name'],
                'desc': ngettext('%(c)s experience', '%(c)s experiences', n) % {'c': n},
                'href': _cat_href(c['name']),
                'icon': _CAT_ICONS.get(slugify(c['name']), _CAT_ICON_DEFAULT),
            }
        )
    return tiles


def _permalink_path(kind: str, slug: str, fallback: str) -> str:
    """Resolve a dynamic nav target through General → Permalinks.

    The resolver is the single source of truth for entity URL shapes; if a
    stored template is invalid or the settings table is missing we keep the
    caller's already-correct hardcoded path rather than emitting a broken link.
    """
    try:
        from core.services.permalinks import resolver_for_settings

        return resolver_for_settings().path(kind, slug=slug)
    except Exception:  # noqa: BLE001 — nav must never break a render
        return fallback


def storefront_nav(request):
    """Inject header megamenu data on every render.

    Category tiles and destination lists are both built live from the DB
    (categories with active experiences, active Place records) so the menu
    never links to a 404 or an empty filter.  Link shapes come from
    General → Permalinks; the hardcoded paths remain the fallback.

    The keys are namespaced ``montenegro_nav_*`` on purpose: the generic
    catalog plugin also exposes ``nav_categories`` and whichever context
    processor ran last used to win, which is how the Montenegro dropdown
    rendered empty rows.
    """
    places, destinations = _nav_places()
    places = {
        column: [
            {**item, 'href': _permalink_path('place', item['slug'], f'/places/{item["slug"]}/')}
            for item in items
        ]
        for column, items in places.items()
    }
    destinations = [
        {**item, 'href': _permalink_path('place', item['slug'], f'/places/{item["slug"]}/')}
        for item in destinations
    ]
    return {
        'storefront_nav': {
            'categories': _nav_categories(),
            'destinations': destinations,
            'places': places,
        },
        # Legacy keys kept for the shipped theme markup; catalog's
        # ``nav_categories`` is left untouched so neither plugin clobbers the
        # other regardless of registration order.
        'nav_categories': _nav_categories(),
        'nav_destinations': destinations,
        'nav_places_coastal': places['coastal'],
        'nav_places_mountains': places['mountains'],
        'nav_places_cities': places['cities'],
        'nav_places_landmarks': places['landmarks'],
        'permalinks': {
            'product': _permalink_path('product', 'sample', '/products/sample/'),
            'booking': _permalink_path('booking', 'sample', '/bookings/sample/'),
            'journal': _permalink_path('journal', 'sample', '/journal/sample/'),
        },
    }
