# Croatia Experience catalogue: real places, experiences, hotels and events (Nov 2026)

## Goal
croatia-experience.me opened empty: 0 places, experiences, hotels and events. Montenegro has
26 places, about 125 experiences, about 110 hotels and 38 events, all from seed commands.
Owner (2026-11-08): "treba napuniti sa realnim lokacijama… što više moguće", so fill Croatia
with real locations, as many as possible.

## Owner decisions (2026-11-08)
- **Experiences:** each one is a real activity at a real place, at a 2026 market price in EUR.
  The host is the store itself, the vendor **Croatia Experience**: no real or invented operator is
  named as host. Real local operators are added when they sign up.
- **Hotels:** real hotels with name, town, region, official star category and a factual
  description. There are **no rooms, rates, ratings or amenities**, and the guest sends an
  enquiry. The vendor is Croatia Experience.
- **Never:** seeded reviews or ratings, a "was" price (`original_price`, EU Omnibus needs price
  history), a bestseller flag, or a claim about a partner who has not agreed.

## Shape
- Data lives in `plugins/installed/booking_marketplace/seed_data/croatia/`, one module per batch.
  Each module exports a list (`PLACES`, `EXPERIENCES`, `HOTELS` or `EVENTS`), and `__init__.py`
  joins them.
- One command, `manage.py seed_croatia`, is idempotent and keyed by slug:
  - it only fills fields that are empty;
  - it refuses to run unless the active theme's country is `HR`, so Montenegro never gets
    Croatian content.
- Experiences go through `products.ensure_product`, so each one extends a catalog Product
  (v0.109).
- A hotel with no rooms shows "Contact for price" on its card, and its page has an enquiry form;
  `stay_book` takes an enquiry with no room type.
- Covers reuse the bundled `seed_assets` images, chosen by type. Real photos are a follow-up.

## Data rules (for every module)
- English, plain and factual. No superlatives the text cannot back up ("best", "most beautiful",
  "hidden gem").
- No prices or opening hours in place, hotel or event text: they change.
- Only facts you are sure of. Leave out anything you are unsure of; never guess.
- Coordinates are real, in decimal degrees, inside Croatia (lat 42.3–46.6, lon 13.4–19.5).
- `region` is one of `istria`, `kvarner`, `zadar`, `sibenik`, `split`, `dubrovnik`, `lika`,
  `zagreb`, `continental`, `other`.
- Slugs are lowercase ASCII with hyphens (`mali-losinj`, `plitvice-lakes-national-park`). The
  name keeps its diacritics (`Mali Lošinj`).
- `external_links` may only use:
  - `https://en.wikipedia.org/wiki/<Exact_Title>`, when you are certain of the title;
  - `https://croatia.hr/en-gb` (Croatian National Tourist Board);
  - a national or nature park's own site, when you know it.

  Every link is checked after generation and a dead one is dropped.
- Python: a module docstring, `from __future__ import annotations`, single quotes, and lines
  under 100 characters (ruff format).

### PLACES (one dict per place; mirror `management/commands/seed_places.py`)
```
{
  'name': 'Rovinj', 'slug': 'rovinj', 'region': 'istria',
  'place_type': 'coastal',      # coastal | mountains | national_parks | cultural | lakes | cities
  'featured': False,            # True only where the brief says so
  'summary': '≤ 160 chars, one sentence',
  'description': '2–3 sentences, ≤ 450 chars',
  'highlights': ['5 real sights or things to do'],
  'overview': '700–900 chars of editorial body',
  'faqs': [{'q': '...', 'a': '...'}],   # 4: worth visiting / getting there / what to do / how long
  'quick_facts': [{'label': ..., 'value': ...}],  # Best time, Ideal for, Time needed,
                                                  # Getting there, Region, Nearest airport
  'good_for': ['5 short lowercase audience tags'],
  'sections': [{'heading': '...', 'body': '450–650 chars'}],   # 3 sections
  'external_links': [{'label': '... — Wikipedia', 'url': '...'}],
  'latitude': 45.0812, 'longitude': 13.6387,
}
```

### EXPERIENCES (mirror `management/commands/_experiences_data.py`, minus host and ratings)
```
{
  'slug': 'split-sea-kayaking-sunset', 'name': '...',
  'category': 'Water Sports',   # Adventure | Water Sports | Culture | Dining | Wine | Wellness
  'region': 'split', 'location': 'Split',   # location = a place name from PLACES
  'price': 45,                  # EUR per person, typical 2026 market price, integer
  'duration_minutes': 180, 'duration_label': '3 hours',
  'short_description': '≤ 200 chars', 'description': 'two paragraphs separated by \n\n',
  'highlights': [5], 'included': [...], 'not_included': [...],
  'itinerary': [{'title': '...', 'detail': '...'}],
  'faqs': [{'q': '...', 'a': '...'}],   # 2–4
  'meeting_point': 'area, exact point confirmed with your booking',
  'latitude': ..., 'longitude': ...,
  'languages': ['English', 'Croatian'],
  'what_to_bring': [...], 'daily_capacity': 12, 'max_guests_per_booking': 8,
}
```

### HOTELS
```
{
  'name': 'Hotel Esplanade Zagreb', 'slug': 'hotel-esplanade-zagreb',
  'property_type': 'hotel',     # hotel | resort | boutique | apartment | villa | guesthouse
                                # | hostel | mountain_lodge
  'star_rating': 5,             # official Croatian category; 0 when unsure
  'region': 'zagreb', 'location': 'Zagreb',   # town
  'short_description': '≤ 200 chars',
  'description': 'two short factual paragraphs: where it is, what it is',
}
```

### EVENTS (mirror `management/commands/seed_events.py`)
```
{
  'name': 'Dubrovnik Summer Festival', 'slug': 'dubrovnik-summer-festival',
  'category': 'culture',        # music | culture | food | tradition | sport
  'region': 'dubrovnik', 'place_slug': 'dubrovnik',   # a slug from PLACES, or ''
  'venue': '...', 'when_label': 'Mid-July to late August', 'month': 7,
  'featured': False, 'summary': '≤ 200 chars', 'description': '2–4 sentences',
  'highlights': [4], 'faqs': [{'q': ..., 'a': ...}],   # 3
  'official_url': '',           # only when certain; checked after generation
}
```

## Result (2026-11-08)
- 110 places, 120 experiences, 152 hotels and 34 events, in every region but `other`.
- `tests/test_croatia_catalogue.py` checks each entry against the model columns, the region and
  type choices, the Croatia bounding box, unique slugs, experience places, event places and the
  owner's forbidden keys, then runs the command twice on a sample.
- Checked against Wikipedia's API: every linked title exists, and each place lies within 15 km of
  the article's coordinates, except Korčula town (the article marks the island) and six articles
  with no coordinates, checked by hand. The checks found and fixed four dead titles, Kumrovec 20 km off,
  Krasno 13 km off and the Cerovac Caves tour placed by Gospić instead of Gračac. The Cerovac Caves
  link goes to Croatian Wikipedia, which has the only article.
- Dropped as uncertain while writing: seven hotels and a few events. Covers are still the seven
  bundled seed images; real photos are the next step.

## Stars and photos (2026-11-08)
- Hotel stars come from the Ministry of Tourism's register of categorised facilities
  (mint.gov.hr, "Popis kategoriziranih ugostiteljskih i turističkih objekata u RH", 31.10.2026).
  Of the 114 hotels the first pass gave stars, 72 matched and 42 were wrong: 10 too low, 16 too
  high, and 16 now 0. Those 16 are either "special standard" or heritage hotels the register
  gives no stars (Lone, the Westin, both Sheratons, Radisson Blu Split, Angelo d'Oro, Isabella's
  two units at 4 and 5 stars), or hotels it does not list. 32 hotels that had 0 got the register's
  stars. Six names were out of date, among them Meliá Coral (now Pelegrin Plava Laguna), Valamar
  Koralj (Krk Sunny Hotel by Valamar) and Spa Golfer (Hotel Terme Sveti Martin); the register
  marks each as "ex …". Not in the register, so possibly closed or registered under another kind:
  Casa Garzotto, Mozart (Opatija), Niko (Zadar), Colentum (Murter), Marjan (Split), Podstine
  (Hvar), Waterman Svpetrus, Bluesun Marina (Tučepi), Arena (Zagreb), Bizovačke toplice, Nehaj,
  Rajna, Lešić Dimitri and the Chillout hostel. The owner decides whether they stay listed.
- Photos: each place and experience names its subject's Wikipedia article. The photo is the
  first Commons *Quality image* in that article's Commons category (Wikidata P373) that is a
  landscape JPEG, at least 1000 px wide, under CC0, public domain, CC BY or CC BY-SA, with no
  extra restrictions. Failing that, it is the article's lead image. Every choice was looked at on
  contact sheets, and about 65 of the 230 were wrong: a football match for Karlovac, Prague's
  Dancing House for Zagreb, a cat for the Cerovac caves, a US aircraft carrier for a sunset sail,
  New Zealand's Blue Lake for Imotski, panoramas too wide to crop. Those were replaced by hand from
  Commons searches, wider than 2:1 refused. 229 rows have a photo; Lopar keeps its stand-in, since
  Commons search kept answering with a Spanish beach of the same name. `seed_croatia` downloads
  them (1280 px) and stores the author and licence.
