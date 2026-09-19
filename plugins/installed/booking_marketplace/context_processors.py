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
                'desc': f'{n} experience{"s" if n != 1 else ""}',
                'href': _cat_href(c['name']),
                'icon': _CAT_ICONS.get(slugify(c['name']), _CAT_ICON_DEFAULT),
            }
        )
    return tiles


def storefront_nav(request):
    """Inject header megamenu data on every render.

    Category tiles and destination lists are both built live from the DB
    (categories with active experiences, active Place records) so the menu
    never links to a 404 or an empty filter.
    """
    places, destinations = _nav_places()
    return {
        'nav_categories': _nav_categories(),
        'nav_destinations': destinations,
        'nav_places_coastal': places['coastal'],
        'nav_places_mountains': places['mountains'],
        'nav_places_cities': places['cities'],
        'nav_places_landmarks': places['landmarks'],
    }
