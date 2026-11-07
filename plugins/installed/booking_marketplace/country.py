"""The country a travel store serves: its regions, its address code and the words that name it (v0.139.0).

Montenegro Experience and Croatia Experience run this one app. The active theme names
the country (`MorpheusTheme.country`: montenegro says `ME`, croatia says `HR`), so a
store deployed with the croatia theme lists Croatian regions, writes `HR` into its
structured data and titles its pages for Croatia with nothing else to set. A theme that
names no country keeps Montenegro, which this app served alone until now.

The Montenegro texts are the exact strings the app used before, so their Serbian
translations still apply. A page that names the country reads it from here, never
from a literal: a second literal is how a Croatian page would have claimed
`addressCountry: ME`.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _l


@dataclass(frozen=True)
class Country:
    code: str  # ISO 3166-1 alpha-2, as structured data publishes it
    name: object  # lazy: "Montenegro"
    # The storefront's second language, besides English: its region names are
    # searchable too ("boka" finds Kotor Bay).
    language: str
    regions: tuple  # ((key, lazy label), …), in browsing order; 'other' last
    # Verifiable geography per region key: what a traveller confirms on a map.
    region_context: dict
    # Words every query on this store may contain without narrowing it.
    search_stop_words: tuple
    # Tourist arrivals in 2025, the investor page's base (its Sources cite it).
    arrivals_2025: int
    text: dict  # purpose → lazy string; see MONTENEGRO for the keys


MONTENEGRO = Country(
    code='ME',
    name=_l('Montenegro'),
    language='sr',
    regions=(
        ('kotor', _l('Kotor Bay')),
        ('budva', _l('Budva Riviera')),
        ('durmitor', _l('Durmitor & the North')),
        ('skadar', _l('Lake Skadar')),
        ('podgorica', _l('Podgorica')),
        ('ulcinj', _l('Ulcinj & the south coast')),
        ('tivat', _l('Tivat & Luštica')),
        ('cetinje', _l('Cetinje & the Old Royal Capital')),
        ('other', _l('Elsewhere in Montenegro')),
    ),
    region_context={
        'kotor': _l(
            'the fjord-like Bay of Kotor, ringed by walled medieval towns and steep mountains'
        ),
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
    },
    search_stop_words=('montenegro', 'crna', 'gora', 'crnoj', 'gori'),
    # MONSTAT, "Arrivals and overnight stays of tourists, total, 2025".
    arrivals_2025=2_728_564,
    text={
        'experiences': _l('Experiences in Montenegro'),
        'experiences_title': _l('Experiences in Montenegro — book with local hosts'),
        'category_experiences': _l('%(category)s experiences in Montenegro'),
        'category_description': _l(
            'Book %(category)s experiences in Montenegro with trusted local hosts '
            '— instant confirmation, free cancellation on most tours.'
        ),
        'query_in': _l('“%(q)s” in Montenegro'),
        'all_regions': _l('All of Montenegro'),
        'elsewhere': _l('Elsewhere in Montenegro'),
        'shop_title': _l('Shop Montenegro — local goods'),
        'shop_description': _l(
            'Locally made Montenegrin products from trusted vendors — shipped '
            'or ready for pickup across the Adriatic coast.'
        ),
        'places_title': _l('Explore Montenegro'),
        'places_description': _l(
            'Destination guides to the best places to visit in Montenegro — the Bay of '
            'Kotor, the Budva Riviera, Durmitor, Lake Skadar and the southern Adriatic '
            'coast.'
        ),
        'regions_title': _l('Explore Montenegro by region'),
        # A plural pair for ngettext (the region count decides the form).
        'regions_count': (
            'Experiences to book in %(count)d region of Montenegro',
            'Experiences to book in %(count)d regions of Montenegro',
        ),
        'events_title': _l('Montenegro Events Calendar'),
        'events_description': _l(
            "What's on in Montenegro through the year — Kotor Carnival, the Mimosa "
            'Festival, Boka Night, summer theatre in Budva, Lake Fest and the winter '
            'ski season.'
        ),
        'event_description': _l('%(name)s in Montenegro. Dates, location and what to expect.'),
        'stays_title': _l('Hotels & stays in Montenegro'),
        'stays_description': _l(
            'Hand-picked hotels, apartments and guesthouses across Montenegro — from the '
            'Bay of Kotor to the Adriatic coast and the northern mountains. Book your stay.'
        ),
        'investors_description': _l(
            'Montenegro Experience: the marketplace for the country’s experiences, '
            'stays and local products, and the market it serves.'
        ),
        'stays_first_visit': _l(
            'The Bay of Kotor combines historic towns, water access and easy day trips. '
            'Budva suits beach-focused stays, while Durmitor is the strongest choice for '
            'hiking.'
        ),
    },
)

CROATIA = Country(
    code='HR',
    name=_l('Croatia'),
    language='hr',
    regions=(
        ('istria', _l('Istria')),
        ('kvarner', _l('Kvarner & the islands')),
        ('zadar', _l('Zadar & Kornati')),
        ('sibenik', _l('Šibenik & Krka')),
        ('split', _l('Split & the central islands')),
        ('dubrovnik', _l('Dubrovnik & the south')),
        ('lika', _l('Lika & Plitvice')),
        ('zagreb', _l('Zagreb')),
        ('continental', _l('Continental Croatia')),
        ('other', _l('Elsewhere in Croatia')),
    ),
    region_context={
        'istria': _l(
            'the Istrian peninsula, with Venetian harbour towns on the coast and hill '
            'towns, vineyards and truffle woods inland'
        ),
        'kvarner': _l(
            'the Kvarner Gulf, with Rijeka, the Opatija Riviera and the islands of Krk, '
            'Cres, Lošinj and Rab'
        ),
        'zadar': _l('Zadar and its islands, between the Kornati archipelago and Paklenica'),
        'sibenik': _l('Šibenik and the waterfalls of Krka National Park'),
        'split': _l("Split, Diocletian's Palace and the islands of Brač, Hvar and Vis"),
        'dubrovnik': _l(
            "Dubrovnik's walled old town, the Elaphiti islands and the Pelješac peninsula"
        ),
        'lika': _l('the Lika highlands, home to the Plitvice Lakes and the Velebit mountains'),
        'zagreb': _l("Zagreb, Croatia's capital and main transport hub"),
        'continental': _l(
            'continental Croatia, from the Zagorje hills to the Slavonian plains on the Danube'
        ),
        'other': _l('Croatia'),
    },
    search_stop_words=('croatia', 'hrvatska', 'hrvatskoj', 'hrvatsku', 'hrvatske'),
    # eVisitor via the Croatian National Tourist Board: "more than 21.8 million" in 2025.
    arrivals_2025=21_800_000,
    text={
        'experiences': _l('Experiences in Croatia'),
        'experiences_title': _l('Experiences in Croatia — book with local hosts'),
        'category_experiences': _l('%(category)s experiences in Croatia'),
        'category_description': _l(
            'Book %(category)s experiences in Croatia with trusted local hosts '
            '— instant confirmation, free cancellation on most tours.'
        ),
        'query_in': _l('“%(q)s” in Croatia'),
        'all_regions': _l('All of Croatia'),
        'elsewhere': _l('Elsewhere in Croatia'),
        'shop_title': _l('Shop Croatia — local goods'),
        'shop_description': _l(
            'Locally made Croatian products from trusted vendors — shipped '
            'or ready for pickup along the Adriatic coast.'
        ),
        'places_title': _l('Explore Croatia'),
        'places_description': _l(
            'Destination guides to the best places to visit in Croatia — Istria, Kvarner, '
            'Dalmatia and its islands, Dubrovnik, the Plitvice Lakes and Zagreb.'
        ),
        'regions_title': _l('Explore Croatia by region'),
        'regions_count': (
            'Experiences to book in %(count)d region of Croatia',
            'Experiences to book in %(count)d regions of Croatia',
        ),
        'events_title': _l('Croatia Events Calendar'),
        'events_description': _l(
            "What's on in Croatia through the year — carnivals, summer festivals, "
            'open-air concerts, wine and food fairs and Advent in Zagreb.'
        ),
        'event_description': _l('%(name)s in Croatia. Dates, location and what to expect.'),
        'stays_title': _l('Hotels & stays in Croatia'),
        'stays_description': _l(
            'Hand-picked hotels, apartments and guesthouses across Croatia — from Istria '
            'and the Dalmatian islands to Dubrovnik and the lakes inland. Book your stay.'
        ),
        'investors_description': _l(
            'Croatia Experience: the marketplace for the country’s experiences, '
            'stays and local products, and the market it serves.'
        ),
        'stays_first_visit': _l(
            'Split and Dubrovnik combine historic old towns, ferries to the islands and easy '
            'day trips. Istria suits food and wine stays, while the Plitvice Lakes are the '
            'strongest choice for hiking.'
        ),
    },
)

_BY_CODE = {c.code: c for c in (MONTENEGRO, CROATIA)}


def current() -> Country:
    """The country of the store this process serves: the active theme's, else Montenegro."""
    try:
        from themes.registry import theme_registry

        code = str(getattr(theme_registry.active, 'country', '') or '').upper()
    except Exception:  # noqa: BLE001 — no theme yet (start-up, migrations): the default
        code = ''
    return _BY_CODE.get(code, MONTENEGRO)


def regions() -> tuple:
    """((key, label), …) of the store's regions, in browsing order."""
    return current().regions


def region_choices() -> list:
    """The region fields' choices: the store's regions (a callable, so a field follows the theme)."""
    return list(current().regions)


def text(key: str):
    return current().text[key]
