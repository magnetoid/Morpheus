# Montenegro search: find what people type, suggest as they type

Design approved by the owner in chat on 2026-10-14. The site-search fix (`/search/` landing on the
empty goods page) shipped on its own as v0.111.3.

## Goal

Search on montenegro-experience.me finds the experiences a visitor means, best matches first,
suggests results while they type, respects the date they pick, and looks and works like a
professional travel site on phone and desktop.

## What is broken today (measured on the live site, 2026-10-14)

- **Multi-word queries find nothing.** The whole query must appear as one substring, so "kayak
  kotor", "rafting tara", "sunset budva", "blue cave tivat" and "wine tasting podgorica" all return
  "No experiences match your search", while "kayak" alone finds 7.
- **No tolerance:**
  - Accents: "zabljak" finds nothing; "Žabljak" works.
  - Serbian: "kajak" finds nothing.
  - Typos: "kayac" finds nothing.
- **No ranking:** results come in "recommended" order whatever was typed.
- **The date is ignored:** `date` is never read, and the sort form drops it.
- **Categories:** the filter matches `category__name__icontains`, so the menu's slug links
  (`?category=water-sports`) show 0 results.
- **No suggestions** as you type.
- **The bar itself:**
  - the desktop placeholder shows "Sear";
  - labels have no `for`;
  - the date field shows a raw "dd. mm. yyyy.";
  - Where lists all 9 regions, empty ones included.
- **The results page:** the heading never reflects the search, active filters are invisible, and
  zero results offer only "Clear filters".
- **Duplicates:** the home page shows the categories three times, and the hero bar and the
  `/bookings/` bar are two separate copies of the same form.

## Scope

**In scope:**
- Matching for experiences (`/bookings/`) and shop goods (`/shop/`).
- A suggestions endpoint.
- One shared search bar (home hero, `/bookings/`, `/shop/`).
- The results page.
- The category filter.
- The home page's duplicate category row.

**Out of scope:**
- Hotels and events text search (they keep their filters).
- AI or semantic search.
- Postgres extensions.
- Other stores' catalog search.
- Translating listing content (that is localization step 1).

## Design

### 1. The search engine: `booking_marketplace/search.py`

A small in-app index of live listings, chosen because it is instant at Montenegro's size
(≈140 listings), needs no database extensions, and behaves the same in tests (sqlite) and in
production (Postgres).

**Normalisation (`fold(text)`):**
- casefold;
- Serbian Cyrillic transliterated to Latin;
- `đ`→`d`;
- other diacritics stripped (NFKD, combining marks dropped);
- everything that is not a letter or a digit becomes a space.

**Fields and weights per listing:**

| Field | Weight |
|---|---|
| name | 10 |
| location | 6 |
| region label (English and Serbian) | 6 |
| category name | 5 |
| highlights | 3 |
| short description | 2 |
| description | 1 |

**Query:**
- fold, split into terms, and drop stopwords: English (the, a, an, in, on, at, of, and, for, with,
  to, from, near, tour, tours, trip) and Serbian (u, na, i, za, sa, od, do, oko, tura, ture, izlet).
  "tour" is generic, so it is never required.
- each remaining term is expanded with a short English–Serbian synonym list, for example:
  kayak/kajak, boat/brod/camac, wine/vino, beach/plaza, canyon/kanjon, hike/hiking/planinarenje/
  pjesacenje, dive/diving/ronjenje, horse/konj/jahanje, yacht/jahta, island/ostrvo, lake/jezero,
  monastery/manastir, fortress/tvrdjava, cooking/kuvanje, sunset/zalazak, fishing/ribolov,
  olive/maslina, honey/med, cheese/sir, rafting, paragliding/paraglajding.

**Matching:** a term matches a field token when any of these holds:
- it equals the token;
- the token starts with it (terms of 2+ characters);
- the term has 5+ characters and is one edit away from the token (insert, delete, substitute or
  transpose).

**Results:**
- Every term must match somewhere (AND).
- An entry's score is the sum, over the terms, of the best field weight that term matched, times
  1.0 for exact, 0.8 for prefix or 0.5 for one-edit.
- Ties go to top picks, then name.
- When AND finds nothing, any-term matching (OR) supplies **close matches**, labelled as such.

**Cache:** built once per process and reused until a listing or category changes. Signals bump a
version number in the shared cache; each process rebuilds when it sees a new version.

### 2. The date filter

- `date=YYYY-MM-DD`. An invalid date is ignored. A past date is ignored with a note: "Choose a
  date from today on".
- A listing stays when it runs that weekday (no windows means every day) and at least one
  departure has a seat that day: capacity minus active bookings. This is the same rule as
  `services.available_sessions`.
- It costs one query for that date's bookings, grouped by listing and departure, with windows
  prefetched.
- The date is kept by sorting and paging, and shown in the heading and filter chips.

### 3. Suggestions as you type

- **Endpoint:** `GET /bookings/suggest/?q=…`. Queries of 2–80 characters; anything else returns
  empty lists.
- **Response:** JSON `{"experiences": [...], "places": [...], "categories": [...]}`:
  - up to 5 experiences: name, url, location, image, price;
  - up to 3 active places: name, url;
  - up to 3 categories: name, url, count.
- **URLs** follow the visitor's language (`/sr/…`).
- **Headers:** `X-Robots-Tag: noindex`; cacheable for 60 seconds.
- **Client:** debounced (150 ms), rendered with DOM methods (never `innerHTML` with server text),
  as an ARIA combobox: arrow keys move, Enter opens, Esc closes.

### 4. One search bar: `booking_marketplace/_search.html` (Montenegro theme)

- **Variants:** `hero` (home), `bar` (`/bookings/`) and `shop` (`/shop/`).
- **What:** a `type=search` input with a clear button, the placeholder "Try kayaking, Kotor,
  wine…", and the suggestion popup.
- **Where:** "All of Montenegro" plus only the regions that have live experiences, with counts.
- **When:** shows "Any date" until set, then "Sat 18 Oct". The native date picker opens on tap.
- **Category:** desktop only.
- **Search** button.
- Every field has a real `<label for>`.
- **Phones (under 768 px) on `/bookings/` and `/shop/`:** a one-line summary ("Kayaking · Kotor
  Bay · Any date") opens a full-screen panel holding the same form. The home hero keeps its card,
  tighter, with Category hidden.
- Behaviour lives in `montenegro/search.js` (deferred) and styles in `refresh.css`. The form
  works without JavaScript.

### 5. The results page (`/bookings/`, and `/shop/` where it applies)

- **Heading** reflects the search:
  - a query: "“kayak” in Kotor Bay";
  - a category: "Water Sports experiences in Montenegro";
  - otherwise the existing heading.
- Below it: "7 experiences", then a removable chip for each active filter (query, where, when,
  category), then "Clear all".
- **Order:** "Best match" (the score) when there is a query; otherwise the existing recommended
  order. The other sorts are unchanged.
- **Zero results:** "No experiences match “kayak kotor” on Sat 18 Oct", then close matches if
  any, popular categories, and "Clear filters".

### 6. The category filter

`category` accepts a slug or an exact name, ignoring case. An unknown value is ignored. New
links use the slug.

### 7. The home page

The hero's category pills go. The category row with counts just below the hero stays, as do the
"Popular Experiences" tabs.

## Language and SEO

- Every new label gets a Serbian (Montenegrin ijekavian) translation; `test_serbian_catalog`
  enforces it.
- Serbian queries work through folding and the synonym list. Listing text stays English until
  localization step 1.
- Search pages stay `noindex` (unchanged). The suggestions endpoint is never linked and is marked
  `noindex`.

## Tests that prove it

- **Engine:**
  - multi-word in any order;
  - accents (zabljak → Žabljak), `đ`, Cyrillic;
  - synonyms (kajak → kayak);
  - one-edit typos (kayac → kayak) and prefixes (kay → kayak);
  - stopwords;
  - ranking (a name match beats a description match);
  - the any-term fallback.
- **List view:**
  - query + region + date + category together;
  - the date rule (weekday window, a full departure);
  - sorting and paging keep the date;
  - the heading and chips;
  - zero results with close matches;
  - category by slug and by name.
- **Suggestions:** JSON shape, length bounds, `/sr/` links, and the text is never trusted as HTML.
- **Templates:**
  - one partial on the home page, `/bookings/` and `/shop/`;
  - labels tied to their fields;
  - the Serbian catalog guard.

## Success criteria

- On the live site, every probe query above returns sensible results, and the before/after table
  goes in the release notes:
  - "kayak kotor" puts Kotor kayak tours first;
  - "zabljak" finds the Durmitor experiences;
  - "kajak" and "kayac" find kayaking;
  - "blue cave tivat" finds the Blue Cave boats from Tivat.
- A date changes the results.
- Suggestions appear as you type.
- Nothing scrolls sideways at 390 px.
