"""Data-grounded copy for stay (hotel) detail pages.

Every string here is composed ONLY from a Property's own stored attributes —
type, region, star rating, amenities, and the real Place names in its region —
so each of the ~68 hotel pages reads uniquely without inventing a single fact.
No LLM, no external calls; pure and stateless, so it unit-tests trivially and is
safe to call per request. It replaces the one boilerplate "Staying in…"
paragraph that repeated verbatim on every hotel (a duplicate-content drag) and
adds a "Best for" audience profile the template renders as icon cards.
"""

from __future__ import annotations

from plugins.installed.booking_marketplace.place_content import _ICON_SVG

# Verifiable geography for each REGIONS key — what a traveller confirms on a map,
# not marketing adjectives.
_REGION_CONTEXT = {
    'kotor': 'the fjord-like Bay of Kotor, ringed by walled medieval towns and steep mountains',
    'budva': "the Budva Riviera, the coast's busiest run of beaches, resorts and old-town nightlife",
    'durmitor': 'the Durmitor highlands, with national-park peaks, the Tara River canyon and winter skiing',
    'skadar': "Lake Skadar, the Balkans' largest lake and a birdwatching and wine-country retreat",
    'podgorica': "Podgorica, Montenegro's capital and main transport hub",
    'ulcinj': 'Ulcinj and the long sandy beaches of the southern coast',
    'tivat': 'Tivat, home to the Porto Montenegro marina and the Luštica peninsula',
    'cetinje': 'Cetinje, the historic royal capital in the hills above the bay',
    'other': 'Montenegro',
}

# amenity slug -> ("Best for" label, icon key from place_content._ICON_SVG).
# Only amenities that imply *who a stay suits* appear here.
_AMENITY_AUDIENCE = {
    'beachfront': ('Beach stays', 'waves'),
    'pool': ('Sun & swimming', 'waves'),
    'sea_view': ('Sea views', 'waves'),
    'spa': ('Spa & unwinding', 'leaf'),
    'restaurant': ('Dining in', 'utensils'),
    'bar': ('Evenings in', 'wine'),
    'family_rooms': ('Families', 'users'),
    'pet_friendly': ('Travelling with pets', 'leaf'),
    'gym': ('Active stays', 'compass'),
    'kitchenette': ('Self-catering', 'utensils'),
    'airport_shuttle': ('Fly-in stays', 'anchor'),
    'parking': ('Road trips', 'compass'),
    'ev_charging': ('EV road trips', 'compass'),
}

# property_type -> ("Best for" label, icon key)
_TYPE_AUDIENCE = {
    'villa': ('Self-catering', 'utensils'),
    'apartment': ('Self-catering', 'utensils'),
    'boutique': ('Design-led stays', 'gem'),
    'resort': ('All-in-one breaks', 'waves'),
    'mountain_lodge': ('Mountain escapes', 'compass'),
    'guesthouse': ('Low-key local stays', 'leaf'),
    'hostel': ('Budget & solo travel', 'wallet'),
}


def _card(label: str, icon_key: str) -> dict:
    return {'label': label, 'icon': _ICON_SVG.get(icon_key, _ICON_SVG['star'])}


def best_for(prop, *, limit: int = 6) -> list:
    """[{'label','icon'}] — an audience profile inferred from real attributes
    only (type, star class, amenities). Deduped by label, capped. Empty is fine;
    the template hides the block."""
    out: list = []
    seen: set = set()

    def add(label: str, icon_key: str) -> None:
        if label not in seen:
            seen.add(label)
            out.append(_card(label, icon_key))

    if prop.property_type in _TYPE_AUDIENCE:
        add(*_TYPE_AUDIENCE[prop.property_type])
    if (prop.star_rating or 0) >= 4:
        add('A refined stay', 'gem')
    for slug in prop.amenities or []:
        if slug in _AMENITY_AUDIENCE:
            add(*_AMENITY_AUDIENCE[slug])
    return out[:limit]


def _oxford(names: list) -> str:
    names = [n for n in names if n]
    if not names:
        return ''
    if len(names) == 1:
        return names[0]
    return ', '.join(names[:-1]) + ' and ' + names[-1]


def location_intro(prop, nearby=None) -> str:
    """A unique, factual "Staying in …" paragraph built from this property's own
    region/type/rating plus the real Place names in its region. Replaces the
    generic paragraph that used to repeat on every hotel."""
    from plugins.installed.booking_marketplace.models import PROPERTY_TYPES, REGIONS

    type_label = dict(PROPERTY_TYPES).get(prop.property_type, 'stay').lower()
    region_ctx = _REGION_CONTEXT.get(prop.region, 'Montenegro')
    loc = prop.location or dict(REGIONS).get(prop.region) or 'Montenegro'
    star = f'{prop.star_rating}-star ' if (prop.star_rating or 0) else ''
    parts = [f'{prop.name} is a {star}{type_label} in {loc}, set in {region_ctx}.']

    names = []
    for pl in nearby or []:
        name = pl.get('name') if isinstance(pl, dict) else getattr(pl, 'name', '')
        if name:
            names.append(name)
    if names:
        parts.append(f'It puts {_oxford(names[:4])} within reach for day trips.')

    parts.append('Check transport links and seasonal travel times before you book.')
    return ' '.join(parts)
