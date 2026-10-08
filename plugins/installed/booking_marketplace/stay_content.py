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

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l
from django.utils.translation import ngettext

from plugins.installed.booking_marketplace.place_content import _ICON_SVG

# Verifiable geography for each REGIONS key — what a traveller confirms on a map,
# not marketing adjectives.
_REGION_CONTEXT = {
    'kotor': _l('the fjord-like Bay of Kotor, ringed by walled medieval towns and steep mountains'),
    'budva': _l(
        "the Budva Riviera, the coast's busiest run of beaches, resorts and old-town nightlife"
    ),
    'durmitor': _l(
        'the Durmitor highlands, with national-park peaks, the Tara River canyon and winter skiing'
    ),
    'skadar': _l(
        "Lake Skadar, the Balkans' largest lake and a birdwatching and wine-country retreat"
    ),
    'podgorica': _l("Podgorica, Montenegro's capital and main transport hub"),
    'ulcinj': _l('Ulcinj and the long sandy beaches of the southern coast'),
    'tivat': _l('Tivat, home to the Porto Montenegro marina and the Luštica peninsula'),
    'cetinje': _l('Cetinje, the historic royal capital in the hills above the bay'),
    'other': _l('Montenegro'),
}

# amenity slug -> ("Best for" label, icon key from place_content._ICON_SVG).
# Only amenities that imply *who a stay suits* appear here.
_AMENITY_AUDIENCE = {
    'beachfront': (_l('Beach stays'), 'waves'),
    'pool': (_l('Sun & swimming'), 'waves'),
    'sea_view': (_l('Sea views'), 'waves'),
    'spa': (_l('Spa & unwinding'), 'leaf'),
    'restaurant': (_l('Dining in'), 'utensils'),
    'bar': (_l('Evenings in'), 'wine'),
    'family_rooms': (_l('Families'), 'users'),
    'pet_friendly': (_l('Travelling with pets'), 'leaf'),
    'gym': (_l('Active stays'), 'compass'),
    'kitchenette': (_l('Self-catering'), 'utensils'),
    'airport_shuttle': (_l('Fly-in stays'), 'anchor'),
    'parking': (_l('Road trips'), 'compass'),
    'ev_charging': (_l('EV road trips'), 'compass'),
}

# property_type -> ("Best for" label, icon key)
_TYPE_AUDIENCE = {
    'villa': (_l('Self-catering'), 'utensils'),
    'apartment': (_l('Self-catering'), 'utensils'),
    'boutique': (_l('Design-led stays'), 'gem'),
    'resort': (_l('All-in-one breaks'), 'waves'),
    'mountain_lodge': (_l('Mountain escapes'), 'compass'),
    'guesthouse': (_l('Low-key local stays'), 'leaf'),
    'hostel': (_l('Budget & solo travel'), 'wallet'),
}


def _card(label: str, icon_key: str) -> dict:
    return {'label': label, 'icon': _ICON_SVG.get(icon_key, _ICON_SVG['star'])}


def best_for(prop, *, limit: int = 6) -> list:
    """[{'label','icon'}] — an audience profile inferred from real attributes
    only (type, star class, amenities). Deduped by label, capped. Empty is fine;
    the template hides the block."""
    out: list = []
    seen: set = set()

    def add(label, icon_key: str) -> None:
        label = str(label)
        if label not in seen:
            seen.add(label)
            out.append(_card(label, icon_key))

    if prop.property_type in _TYPE_AUDIENCE:
        add(*_TYPE_AUDIENCE[prop.property_type])
    if (prop.star_rating or 0) >= 4:
        add(_('A refined stay'), 'gem')
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
    return _('%(head)s and %(last)s') % {'head': ', '.join(names[:-1]), 'last': names[-1]}


def location_intro(prop, nearby=None) -> str:
    """A unique, factual "Staying in …" paragraph built from this property's own
    region/type/rating plus the real Place names in its region. Replaces the
    generic paragraph that used to repeat on every hotel."""
    from plugins.installed.booking_marketplace.models import PROPERTY_TYPES, REGIONS

    # Whole sentences go to the translator: Serbian puts the star class after
    # the type and declines the place, so no fragment can be glued in English
    # order.
    type_label = str(dict(PROPERTY_TYPES).get(prop.property_type) or _('stay')).lower()
    region_ctx = str(_REGION_CONTEXT.get(prop.region) or _('Montenegro'))
    loc = prop.location or str(dict(REGIONS).get(prop.region) or _('Montenegro'))
    stars = prop.star_rating or 0
    star = ngettext('%(n)s-star ', '%(n)s-star ', stars) % {'n': stars} if stars else ''
    parts = [
        _('%(name)s is a %(star)s%(type)s in %(loc)s, set in %(region)s.')
        % {'name': prop.name, 'star': star, 'type': type_label, 'loc': loc, 'region': region_ctx}
    ]

    names = []
    for pl in nearby or []:
        name = pl.get('name') if isinstance(pl, dict) else getattr(pl, 'name', '')
        if name:
            names.append(name)
    if names:
        parts.append(
            _('It puts %(places)s within reach for day trips.') % {'places': _oxford(names[:4])}
        )

    parts.append(_('Check transport links and seasonal travel times before you book.'))
    return ' '.join(parts)
