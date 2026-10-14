# Montenegro Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Search on montenegro-experience.me finds the experiences a visitor means, best match first, respects the date they pick, suggests results while they type, and works as one professional search bar on phone and desktop.

**Architecture:** A pure-Python engine (`booking_marketplace/search.py`) folds text and ranks documents. A per-process index of the store's listings and places is versioned through the shared cache and rebuilt when a listing, place or category changes. `search_page.py` turns a request into validated search values and into the page's words (heading, chips, empty-state line, suggestions). The list views filter in the database first (region, category, date via `services.bookable_on`), then let the engine rank what survives. The Montenegro theme gets one search-bar partial with three variants, a deferred `search.js` (suggestions, date label, phone panel) and new rules in `refresh.css`.

**Tech Stack:** Django views, templates and template tags; the shared Django cache; Babel (already installed through py-moneyed) for CLDR date labels; vanilla JavaScript with no build step; the gettext `sr` catalog.

**Spec:** `docs/superpowers/specs/2026-10-14-montenegro-search-design.md` (approved by the owner on 2026-10-14).

## Global Constraints

- **Ownership.**
  - The engine, views, URL and template tags live in `plugins/installed/booking_marketplace/`.
  - Markup, CSS and JavaScript live in the Montenegro theme (`themes/library/montenegro/`).
  - The one change outside those is analytics' pageview rule (Task 5, decision 7).
  - Nothing in `core/`, `storefront`, `seo` or `admin_dashboard` changes.
- **Serbian.** Every new msgid, in a template or in Python, gets a Serbian (Montenegrin ijekavian, Latin script) `msgstr` in `locale/sr/LC_MESSAGES/django.po`.
  - Entries with placeholders carry `#, python-format`.
  - Before adding a msgid, `grep -nF 'msgid "<text>"'` the file: `msgfmt` refuses a duplicate. `"Clear all"` already exists.
  - Compile with `msgfmt --check-format -o locale/sr/LC_MESSAGES/django.mo locale/sr/LC_MESSAGES/django.po`.
  - `booking_marketplace/tests/test_serbian_catalog.py` guards the templates.
- **No new dependency.** Babel is used only inside `search_page.date_label`, which falls back to ISO format if Babel is missing.
- **Text is data.**
  - What a visitor types and what a listing says are rendered through autoescaped templates and returned as JSON strings.
  - `search.js` sets text with `textContent` only. It never uses `innerHTML`, `outerHTML`, `insertAdjacentHTML` or `document.write`.
  - `search.js` follows a link only when it is a path on this site (`/…`, not `//…`).
- **No JavaScript needed.** The form works without JavaScript, and `search.js` is loaded with `defer`.
- **CSS.**
  - New rules go in `themes/library/montenegro/static/montenegro/refresh.css`. `tailwind.css` is precompiled, so a utility class it never saw does not exist.
  - Never write `*/` inside a CSS comment.
  - Nothing may scroll sideways at 390 px.
- **Test assertions.** Tests assert on unique markers: ids, `data-` attributes and slugs. Visible words are asserted only where the words are the feature (headings, labels, messages).
- **Test command.** `$TEST` means `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace' .venv/bin/python manage.py test`, run from `/Users/magnetoid/coding/morph`.
- **Gates before pushing:**
  - ruff 0.15.8 `check .` and `format --check .`
  - `manage.py check`
  - `makemigrations --check --dry-run`
  - `scripts/check_core_boundary.py`, `check_plugin_boundary.py` and `check_plugin_standard.py`
  - `manage.py release --check`
  - the full suite, with `MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress'`
- **Where to work.**
  - Use branch `feat/montenegro-search` in `/Users/magnetoid/coding/morph`. The owner works in that one folder, so no worktree.
  - Leave the untracked files already there alone: `.janus/`, `site/`, `*.png`, `uv.lock`, `supernatural-missing-images.txt` and `docs/plans/montenegro-cutover-status-2026-09-19.md`.
  - Merging to `main` deploys all stores, and happens only in Task 9.
- **Commit messages** end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Decisions this plan takes beyond the spec (each can be reversed before execution)

1. **Typos only when a word finds nothing.** A one-letter typo is tried only when a word matches nothing as typed, through its singular or through a synonym.
   - The spec allowed a typo for every word of five or more letters. Tried on the live content, that made "hiking" bring up the biking tours, "beach" match "reach" and "boats" match "boots".
   - "kayac", "hikng" and "rafitng" still find kayaking, hiking and rafting.
   - A plural also looks for its singular ("boats" finds "boat", "beaches" finds "beach").
2. **Store-wide words are stopwords**, like "tour":
   - montenegro, crna, gora, crnoj, gori
   - experience, experiences, activity, activities, dozivljaj, dozivljaji
   - trips, izleti

   Without this, "kayak montenegro" would drop every kayak tour whose text never names the country.
3. **Matching stays inside the filters.** "Every word" and the close matches are worked out within the region, date and category filters. "kayak budva" with Where set to Kotor Bay then offers Kotor's kayak tours as close matches, rather than nothing.
4. **The suggestion popup lists only full matches.** It shows only what matches every word typed. The shop bar has no popup: its 17 goods fit on one screen and the endpoint answers experiences, places and categories (spec §3).
5. **The intro hides during a search.** The intro paragraph under the heading is hidden while a search or filter is active, so the results start higher on the page.
6. **Searches report `SEARCH_PERFORMED`**, like the storefront's own search does. That feeds search trends, the zero-result report and GA4's search event. Close matches count as zero results.
7. **Analytics no longer counts non-HTML responses as pageviews.**
   - Every response to a storefront GET was recorded as a pageview. Each suggestion fetch would have been one, and the cookie banner's `/csrf/` fetch already is.
   - This is a one-line rule in `analytics/middleware.py`.
8. **Dates use CLDR** (Babel on the server, `Intl` in the browser). Django's own `sr` day and month names are Cyrillic: the live booking widget on `/sr/` shows "суб." and "Окт.". Dates read "Sun 18 Oct" and "ned 18. okt".

## Review Focus

1. **Huge or odd queries.**
   - Inputs: a 5,000-character query, punctuation only, or only stopwords.
   - Expected: the page answers 200 without delay. Punctuation-only and stopword-only queries mean "no text filter".
   - Pinned by `test_a_long_query_is_capped` and `test_nothing_to_search_for` (Task 1), and `test_a_huge_query_still_answers` (Task 4).
2. **Text stays text.**
   - Inputs: a query holding `<script>`, or a listing named with markup.
   - Expected: the query is escaped in the heading, chips and input. The listing name reaches the JSON verbatim, and `search.js` never parses it.
   - Pinned by `test_the_query_is_escaped` (Task 7), `test_text_is_data` (Task 5) and `test_the_script_never_writes_html` (Task 6).
3. **A stale index.**
   - Inputs: a rename, deactivation or category rename through `save()`; another process's bump; a lost cache key; an edit through `QuerySet.update()`.
   - Expected: the next search, or the next one after `MAX_AGE_S`, sees the change.
   - Pinned by the `StoreIndexTests` cases (Task 2).
4. **Serbian pages.**
   - Expected on `/sr/`: suggestion and category links carry `/sr/`, headings and messages are Serbian, and date labels are Latin (no Cyrillic).
   - Pinned by `test_links_stay_in_serbian` (Task 5), `test_the_bar_follows_the_language` (Task 6) and `test_serbian_heading` (Task 7).
5. **Dates at the edges.**
   - Inputs: today, yesterday, an impossible date, a listing with departure times against one without, and cancelled bookings.
   - Expected: today is allowed. A past date is ignored with a note. Departures are counted the way `available_sessions` counts them.
   - Pinned by `BookableOnTests` (Task 3), and by `test_a_past_date_is_ignored_with_a_note` and `test_today_counts_and_nonsense_is_ignored` (Task 4).

## Files

**Create**
- `plugins/installed/booking_marketplace/search.py`: the engine (fold, query terms, `Index`) and the store's cached index (`documents`, `listing_index`, `bump`).
- `plugins/installed/booking_marketplace/search_page.py`: the request as validated values (`read_params`), the date label, the page's words, suggestions, and the bar's context.
- `themes/library/montenegro/templates/booking_marketplace/_search.html`: the one search bar, in hero, bar and shop variants.
- `themes/library/montenegro/static/montenegro/search.js`: suggestions, the date label, the clear buttons and the phone panel.
- Tests in `plugins/installed/booking_marketplace/tests/`:
  - `test_search_engine.py`
  - `test_search_index.py`
  - `test_bookable_on.py`
  - `test_search_results.py`
  - `test_search_suggest.py`
  - `test_search_bar.py`
  - `test_search_results_page.py`
  - `test_search_home.py`
- `plugins/installed/analytics/tests/test_pageviews_are_pages.py`.

**Modify**
- `plugins/installed/booking_marketplace/`:
  - `services.py`: `bookable_on`, `live_regions`, and `active_categories` gains `slug`.
  - `views.py`: `services_list`, `products_list`, `suggest`.
  - `urls.py`: `bookings/suggest/`.
  - `app.py`: signals that bump the index.
  - `templatetags/booking_tags.py`: `search_bar`, `_cat_href` by slug, and three tags removed.
  - `context_processors.py`: the menu links by slug.
  - `tests/test_nav_derived.py`.
- `plugins/installed/analytics/middleware.py`: count only HTML pages.
- `themes/library/montenegro/`:
  - `templates/booking_marketplace/list.html`
  - `templates/storefront/home.html`
  - `static/montenegro/refresh.css`
- `locale/sr/LC_MESSAGES/django.po` and `django.mo`.
- `CLAUDE.md`, the spec's status line, `docs/RELEASE_NOTES.md` and `morph/settings.py`, through `manage.py release`.

**Delete**
- `themes/library/montenegro/templates/booking_marketplace/_search_bar.html`, replaced by `_search.html`.

## Pre-flight: shared interfaces

| Producer → consumer | What crosses | Check |
|---|---|---|
| Task 1 → Tasks 2, 4, 5 | `Doc(key, kind, fields)`, `Term`, `Matches(scores, close)`, `parse_query(q) -> list[Term]`, `Index(docs).find(terms, *, kind, within=None, fallback=True) -> Matches \| None` | `find` returns None only for empty terms |
| Task 2 → Tasks 4, 5 | `search.listing_index() -> Index`, `search.bump(**kw)`, `search._STATE`, `search._VERSION_KEY`, `search.MAX_AGE_S` | kinds in the index: `'experience'`, `'product'`, `'place'` |
| Task 3 → Task 4 | `services.bookable_on(services, day) -> list` (keeps the given order) | accepts a QuerySet or a list |
| Task 4 → Tasks 5–7 | `search_page.SearchParams`, `read_params(request)`, `date_label(day)`, `date_locale()`, `values(params)`, `page_context(request, params, *, close=False, kind='experience')`, context keys `search`, `q`, `region`, `category` (a slug), `sort` | `values()` keys: `q region region_label date_iso date_label date_note category category_label` |
| Task 5 → Task 6 | URL `/bookings/suggest/` (name `booking_marketplace:suggest`), JSON keys `experiences places categories` | the bar computes the URL with `localized_path`, never `{% url %}` |
| Task 6 → Tasks 7, 8 | `{% include "booking_marketplace/_search.html" with variant=… %}`, `services.active_categories()` rows `{name, slug, count}` | the home page and `list.html` include the same partial |

---

### Task 1: The search engine

**Files:**
- Create: `plugins/installed/booking_marketplace/search.py`
- Test: `plugins/installed/booking_marketplace/tests/test_search_engine.py`

**Interfaces:**
- Produces:
  - `fold(text) -> str`
  - `index_tokens(text) -> set[str]`
  - `one_edit(a, b) -> bool`
  - `parse_query(q) -> list[Term]`
  - `Doc(key, kind, fields)`, `Term(text, variants)`, `Matches(scores, close)`
  - `Index(docs).find(terms, *, kind, within=None, fallback=True) -> Matches | None`
  - `EXACT`, `PREFIX`, `TYPO`, `MAX_QUERY_CHARS = 200` and `MAX_TERMS = 8`

- [ ] **Step 0: Branch**

```bash
cd /Users/magnetoid/coding/morph && git checkout -b feat/montenegro-search
```

- [ ] **Step 1: Write the failing tests**

Create `plugins/installed/booking_marketplace/tests/test_search_engine.py`:

```python
"""The search engine finds what a visitor types (booking_marketplace/search.py).

Pure Python, no database: documents go in, ranked keys come out. Live on 2026-10-14
every multi-word query found nothing, "zabljak" missed Žabljak, "kajak" and "kayac"
missed the kayak tours, and results came in the same order whatever was typed.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from plugins.installed.booking_marketplace import search
from plugins.installed.booking_marketplace.search import Doc, Index, fold, one_edit, parse_query


def _doc(key, name, *, location='', region='', description='', kind='experience'):
    return Doc(key, kind, ((10, name), (6, location), (6, region), (1, description)))


DOCS = [
    _doc('kotor-kayak', 'Sunset Kayak Tour on the Bay of Kotor', location='Kotor',
         region='Kotor Bay Boka Kotorska'),
    _doc('budva-kayak', 'Kayak and Snorkel Tour to Sveti Nikola Island', location='Budva',
         region='Budva Riviera'),
    _doc('kotor-walk', 'Kotor Old Town Walk', location='Kotor', region='Kotor Bay Boka Kotorska',
         description='Ends at the kayak harbour.'),
    _doc('zabljak-hike', 'Durmitor Day Hike', location='Žabljak', region='Durmitor & the North'),
    _doc('tara-zipline', 'Zipline across the Tara Canyon', location='Đurđevića Tara',
         region='Durmitor & the North'),
    _doc('biking', 'Mountain Biking above Kolašin', location='Kolašin', region='Durmitor & the North'),
    _doc('honey', 'Wild Mountain Honey', kind='product'),
    _doc('kotor-place', 'Kotor', region='Kotor Bay Boka Kotorska', kind='place'),
]


def _find(q, kind='experience', **kwargs):
    return Index(DOCS).find(parse_query(q), kind=kind, **kwargs)


def _ranked(q, **kwargs):
    found = _find(q, **kwargs)
    return sorted(found.scores, key=lambda key: (-found.scores[key], key))


class FoldTests(SimpleTestCase):
    def test_accents_case_and_cyrillic_fold_to_one_word(self):
        self.assertEqual(fold('Žabljak'), 'zabljak')
        self.assertEqual(fold('ŽABLJAK'), 'zabljak')
        self.assertEqual(fold('Жабљак'), 'zabljak')
        self.assertEqual(fold('Đurđevića Tara'), 'durdevica tara')
        self.assertEqual(fold('Herceg Novi’s fortress, 3-day'), 'herceg novi s fortress 3 day')

    def test_a_word_with_dj_is_indexed_both_ways(self):
        self.assertEqual(search.index_tokens('Đurđevića'), {'durdevica', 'djurdjevica'})

    def test_one_edit(self):
        for a, b in (('kayac', 'kayak'), ('hikng', 'hiking'), ('rafitng', 'rafting'), ('kayaks', 'kayak')):
            with self.subTest(a=a, b=b):
                self.assertTrue(one_edit(a, b))
        for a, b in (('kayak', 'kayak'), ('kotor', 'budva'), ('kayac', 'kayaking'), ('ab', 'cd')):
            with self.subTest(a=a, b=b):
                self.assertFalse(one_edit(a, b))


class QueryTests(SimpleTestCase):
    def test_stopwords_and_repeats_are_dropped(self):
        words = [term.text for term in parse_query('Kayak tours in the Bay of Kotor, kayak')]
        self.assertEqual(words, ['kayak', 'bay', 'kotor'])

    def test_store_wide_words_are_stopwords(self):
        self.assertEqual(parse_query('Experiences in Montenegro'), [])
        self.assertEqual(parse_query('izleti u Crnoj Gori'), [])

    def test_a_long_query_is_capped(self):
        terms = parse_query(' '.join(f'word{i}' for i in range(500)))
        self.assertEqual(len(terms), search.MAX_TERMS)
        self.assertLessEqual(sum(len(term.text) for term in terms), search.MAX_QUERY_CHARS)

    def test_synonyms_and_singulars_are_variants(self):
        (term,) = parse_query('kajaks')
        self.assertEqual(term.text, 'kajaks')
        self.assertIn('kajak', term.variants)
        self.assertIn('kayak', term.variants)


class MatchingTests(SimpleTestCase):
    def test_every_word_must_match_in_any_order(self):
        self.assertEqual(_ranked('kayak kotor'), ['kotor-kayak', 'kotor-walk'])
        self.assertEqual(_ranked('kotor kayak'), ['kotor-kayak', 'kotor-walk'])

    def test_a_name_match_ranks_above_a_description_match(self):
        ranked = _ranked('kayak')
        self.assertEqual(set(ranked[:2]), {'kotor-kayak', 'budva-kayak'})
        self.assertEqual(ranked[2:], ['kotor-walk'])

    def test_accents_and_cyrillic(self):
        for q in ('zabljak', 'Žabljak', 'Жабљак'):
            with self.subTest(q=q):
                self.assertEqual(_ranked(q), ['zabljak-hike'])

    def test_dj_is_read_both_ways(self):
        for q in ('durdevica', 'djurdjevica', 'Đurđevića'):
            with self.subTest(q=q):
                self.assertEqual(_ranked(q), ['tara-zipline'])

    def test_a_serbian_word_finds_the_english_listing(self):
        self.assertEqual(set(_ranked('kajak')), {'kotor-kayak', 'budva-kayak', 'kotor-walk'})

    def test_a_typo_and_a_prefix(self):
        self.assertEqual(set(_ranked('kayac')), {'kotor-kayak', 'budva-kayak', 'kotor-walk'})
        self.assertEqual(set(_ranked('kay')), {'kotor-kayak', 'budva-kayak', 'kotor-walk'})

    def test_a_word_that_matches_is_not_read_as_a_typo(self):
        # "hiking" is one letter from "biking"; its synonym "hike" matches, so no typo is tried.
        self.assertEqual(_ranked('hiking'), ['zabljak-hike'])

    def test_close_matches_when_no_listing_has_every_word(self):
        found = _find('kayak ulcinj')
        self.assertTrue(found.close)
        self.assertEqual(set(found.scores), {'kotor-kayak', 'budva-kayak', 'kotor-walk'})

    def test_no_close_matches_without_the_fallback(self):
        self.assertEqual(_find('kayak ulcinj', fallback=False), search.Matches({}, close=False))

    def test_nothing_to_search_for(self):
        self.assertIsNone(_find('the tour'))
        self.assertIsNone(_find('  ?!  '))

    def test_kind_and_within_restrict_the_keys(self):
        self.assertEqual(_ranked('honey'), [])
        self.assertEqual(sorted(_find('honey', kind='product').scores), ['honey'])
        self.assertEqual(sorted(_find('med', kind='product').scores), ['honey'])
        self.assertEqual(sorted(_find('kotor', kind='place').scores), ['kotor-place'])
        self.assertEqual(_ranked('kayak', within={'budva-kayak'}), ['budva-kayak'])
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_engine`
Expected: ERROR — `ImportError: cannot import name 'search' from 'plugins.installed.booking_marketplace'` (the module does not exist yet).

- [ ] **Step 3: Write the engine**

Create `plugins/installed/booking_marketplace/search.py`:

```python
"""Search for the travel store: what a visitor types, best match first.

docs/superpowers/specs/2026-10-14-montenegro-search-design.md. Text is folded before it
is compared (case, accents, Serbian Cyrillic, `đ`), so `zabljak`, `ŽABLJAK` and `Жабљак`
are one word. A query word matches a listing's word when it is the same word, the start
of it, its singular or a Serbian synonym, or, when nothing matched as typed, one typo
away. Every word must match; when no listing has them all, listings with any of them come
back as close matches. Where a word matched decides the score: the name counts most, the
description least.

Pure Python over `Doc`s; the store's own index (its listings and places, cached per
process) is built at the end of this module.
"""

from __future__ import annotations

import bisect
import re
import unicodedata
from typing import NamedTuple

EXACT, PREFIX, TYPO = 1.0, 0.8, 0.5
MAX_QUERY_CHARS = 200
MAX_TERMS = 8

STOPWORDS = frozenset(
    {
        # English
        'the', 'a', 'an', 'in', 'on', 'at', 'of', 'and', 'for', 'with', 'to', 'from', 'near',
        'tour', 'tours', 'trip', 'trips',
        # Serbian
        'u', 'na', 'i', 'za', 'sa', 'od', 'do', 'oko', 'tura', 'ture', 'izlet', 'izleti',
        # The whole store is Montenegro, and everything on it is an experience
        'montenegro', 'crna', 'gora', 'crnoj', 'gori',
        'experience', 'experiences', 'activity', 'activities', 'dozivljaj', 'dozivljaji',
    }
)

# English–Serbian spellings of one meaning, written folded: any of them finds the others.
SYNONYM_GROUPS = (
    ('kayak', 'kajak'),
    ('boat', 'brod', 'camac'),
    ('wine', 'vino'),
    ('winery', 'vinarija'),
    ('beach', 'plaza'),
    ('canyon', 'kanjon'),
    ('hike', 'hiking', 'planinarenje', 'pjesacenje'),
    ('dive', 'diving', 'ronjenje'),
    ('horse', 'konj', 'jahanje'),
    ('yacht', 'jahta'),
    ('island', 'ostrvo'),
    ('lake', 'jezero'),
    ('monastery', 'manastir'),
    ('fortress', 'tvrdjava', 'tvrdava'),
    ('cooking', 'kuvanje', 'kuhanje'),
    ('sunset', 'zalazak'),
    ('fishing', 'ribolov', 'pecanje'),
    ('olive', 'maslina', 'maslinovo'),
    ('honey', 'med'),
    ('cheese', 'sir'),
    ('paragliding', 'paraglajding'),
    ('cave', 'pecina'),
    ('river', 'rijeka'),
    ('mountain', 'planina'),
    ('tasting', 'degustacija'),
    ('walk', 'walking', 'setnja'),
    ('bike', 'cycling', 'bicikl', 'biciklizam'),
    ('jeep', 'dzip'),
    ('adventure', 'avantura'),
    ('culture', 'kultura'),
    ('food', 'hrana'),
)
_SYNONYMS = {word: group for group in SYNONYM_GROUPS for word in group}

# Lowercase Serbian Cyrillic to Latin, accents kept (they are dropped with all the others).
_CYRILLIC = str.maketrans(
    {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'ђ': 'đ', 'е': 'e', 'ж': 'ž',
        'з': 'z', 'и': 'i', 'ј': 'j', 'к': 'k', 'л': 'l', 'љ': 'lj', 'м': 'm', 'н': 'n',
        'њ': 'nj', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'ћ': 'ć', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'č', 'џ': 'dž', 'ш': 'š',
    }
)
_WORD = re.compile(r'[^\W_]+')


class Doc(NamedTuple):
    """Something to find: its key (a pk), its kind and its (weight, text) fields."""

    key: object
    kind: str
    fields: tuple


class Term(NamedTuple):
    """A query word and the spellings that count as it (its singular, its synonyms)."""

    text: str
    variants: tuple


class Matches(NamedTuple):
    """Score per key. `close`: no key matched every word, and these match some."""

    scores: dict
    close: bool


def _latin(text: str) -> str:
    return (text or '').casefold().translate(_CYRILLIC)


def _words(text: str) -> list[str]:
    text = unicodedata.normalize('NFKD', text)
    return _WORD.findall(''.join(ch for ch in text if not unicodedata.combining(ch)))


def fold(text: str) -> str:
    """Lowercase Latin without accents, one space between words; `đ` becomes `d`."""
    return ' '.join(_words(_latin(text).replace('đ', 'd')))


def index_tokens(text: str) -> set[str]:
    """A document's words. A word with `đ` is kept both ways (`durdevica`, `djurdjevica`):
    a visitor without a Serbian keyboard types either."""
    raw = _latin(text)
    words = set(_words(raw.replace('đ', 'd')))
    if 'đ' in raw:
        words.update(_words(raw.replace('đ', 'dj')))
    return words


def one_edit(a: str, b: str) -> bool:
    """Whether `b` is `a` with one letter added, dropped or changed, or two neighbours swapped."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i, (x, y) in enumerate(zip(a, b, strict=True)) if x != y]
        if len(diff) == 1:
            return True
        i, j = diff[0], diff[-1]
        return len(diff) == 2 and j == i + 1 and a[i] == b[j] and a[j] == b[i]
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    i = 0
    while i < len(short) and short[i] == long_[i]:
        i += 1
    return short[i:] == long_[i + 1 :]


def _forms(word: str) -> set[str]:
    """The word and its singular: `boats` also looks for `boat`, `beaches` for `beach`."""
    forms = {word}
    if len(word) >= 4 and word.endswith('s') and not word.endswith('ss'):
        forms.add(word[:-1])
        if len(word) >= 5 and word.endswith('es'):
            forms.add(word[:-2])
    return forms


def parse_query(q: str) -> list[Term]:
    """The query's words, folded, without stopwords or repeats, each with its variants."""
    terms: list[Term] = []
    seen: set[str] = set()
    for word in fold((q or '')[:MAX_QUERY_CHARS]).split():
        if word in STOPWORDS or word in seen:
            continue
        seen.add(word)
        variants: set[str] = set()
        for form in _forms(word):
            variants.add(form)
            variants.update(_SYNONYMS.get(form, ()))
        variants.discard(word)
        terms.append(Term(word, tuple(sorted(variants))))
        if len(terms) == MAX_TERMS:
            break
    return terms


class Index:
    """Folded words → {key: the best field weight the word appears in}, over `Doc`s."""

    def __init__(self, docs) -> None:
        postings: dict[str, dict] = {}
        self._kinds: dict = {}
        for doc in docs:
            self._kinds[doc.key] = doc.kind
            for weight, text in doc.fields:
                for token in index_tokens(text):
                    row = postings.setdefault(token, {})
                    if weight > row.get(doc.key, 0):
                        row[doc.key] = weight
        self._postings = postings
        self._vocab = sorted(postings)
        self._by_len: dict[int, list[str]] = {}
        for token in self._vocab:
            self._by_len.setdefault(len(token), []).append(token)

    def _lookup(self, word: str, *, prefix: bool) -> list[tuple[str, float]]:
        hits = [(word, EXACT)] if word in self._postings else []
        if prefix:
            i = bisect.bisect_right(self._vocab, word)
            while i < len(self._vocab) and self._vocab[i].startswith(word):
                hits.append((self._vocab[i], PREFIX))
                i += 1
        return hits

    def _hits(self, term: Term) -> list[tuple[str, float]]:
        """The words `term` matches, and how well. A typo is tried only when nothing
        matched as typed: `hiking` must not bring the biking tours, nor `beach` "reach"."""
        hits = self._lookup(term.text, prefix=len(term.text) >= 2)
        for variant in term.variants:
            hits += self._lookup(variant, prefix=len(variant) >= 4)
        if hits or len(term.text) < 5:
            return hits
        size = len(term.text)
        return [
            (token, TYPO)
            for length in (size - 1, size, size + 1)
            for token in self._by_len.get(length, ())
            if one_edit(term.text, token)
        ]

    def _scores(self, term: Term, kind: str, within) -> dict:
        best: dict = {}
        for token, quality in self._hits(term):
            for key, weight in self._postings[token].items():
                if self._kinds[key] != kind or (within is not None and key not in within):
                    continue
                score = weight * quality
                if score > best.get(key, 0.0):
                    best[key] = score
        return best

    def find(self, terms, *, kind: str, within=None, fallback: bool = True) -> Matches | None:
        """Keys of `kind` (only those in `within`, when given) matching every term, scored.

        None when there is nothing to look for. When no key matches every term and
        `fallback` is on, the keys matching any term come back as close matches.
        """
        if not terms:
            return None
        per_term = [self._scores(term, kind, within) for term in terms]
        every = set(per_term[0]).intersection(*per_term[1:])
        if every:
            return Matches({key: sum(s[key] for s in per_term) for key in every}, close=False)
        if not fallback:
            return Matches({}, close=False)
        some = set().union(*per_term)
        return Matches(
            {key: sum(s.get(key, 0.0) for s in per_term) for key in some}, close=bool(some)
        )
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_engine`
Expected: `Ran 18 tests` … `OK`.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check --fix plugins/installed/booking_marketplace/search.py plugins/installed/booking_marketplace/tests/test_search_engine.py
.venv/bin/ruff format plugins/installed/booking_marketplace/search.py plugins/installed/booking_marketplace/tests/test_search_engine.py
git add plugins/installed/booking_marketplace/search.py plugins/installed/booking_marketplace/tests/test_search_engine.py
git commit -m "feat(booking): a search engine that folds accents, Cyrillic, Serbian and typos" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: The store's index follows its listings

**Files:**
- Modify: `plugins/installed/booking_marketplace/search.py` (imports; append the store index)
- Modify: `plugins/installed/booking_marketplace/app.py` (`ready()`: connect the signals)
- Test: `plugins/installed/booking_marketplace/tests/test_search_index.py`

**Interfaces:**
- Consumes: Task 1's `Doc` and `Index`.
- Produces:
  - `search.documents() -> list[Doc]`: kinds `'experience'`, `'product'` and `'place'`, keyed by pk.
  - `search.listing_index() -> Index`
  - `search.bump(**kwargs) -> None`
  - Module state `search._STATE` (`{'built': (version, monotonic_at, Index)}`), `search._VERSION_KEY` and `search.MAX_AGE_S = 600`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/installed/booking_marketplace/tests/test_search_index.py`:

```python
"""The store's search index follows its listings (booking_marketplace/search.py).

The index lives in each web process. A listing, place or category saved or deleted
anywhere bumps a version token in the shared cache, and every process rebuilds before
its next search; an edit that skips save() (QuerySet.update() in the seed commands) is
picked up once the index is MAX_AGE_S old.
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace import search
from plugins.installed.booking_marketplace.models import BookableService, Place
from plugins.installed.catalog.models import Category, Vendor


class StoreIndexTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        self.water = Category.objects.create(name='Water Sports', slug='water-sports')
        self.kayak = BookableService.objects.create(
            vendor=self.vendor,
            name='Sunset Kayak Tour',
            slug='sunset-kayak',
            location='Herceg Novi',
            region='kotor',
            category=self.water,
            highlights=['Glass-bottom view of the reef'],
            short_description='<p>Paddle under the walls.</p>',
            description='Ends with grilled sardines.',
            price=Money(50, 'EUR'),
        )

    def _found(self, q, kind='experience'):
        found = search.listing_index().find(search.parse_query(q), kind=kind)
        return set(found.scores) if found else set()

    def test_every_field_a_visitor_types(self):
        # name, location, region (English and Serbian), category, highlights, summary, text
        for q in ('sunset', 'herceg', 'kotor bay', 'boka', 'water', 'glass', 'paddle', 'sardines'):
            with self.subTest(q=q):
                self.assertEqual(self._found(q), {self.kayak.pk})

    def test_a_rename_reaches_the_next_search(self):
        self.assertEqual(self._found('sunset'), {self.kayak.pk})
        self.kayak.name = 'Morning Kayak Tour'
        self.kayak.save()
        self.assertEqual(self._found('sunset'), set())
        self.assertEqual(self._found('morning'), {self.kayak.pk})

    def test_a_deactivated_or_deleted_listing_leaves(self):
        self.kayak.is_active = False
        self.kayak.save()
        self.assertEqual(self._found('sunset'), set())
        self.kayak.is_active = True
        self.kayak.save()
        self.assertEqual(self._found('sunset'), {self.kayak.pk})
        self.kayak.delete()
        self.assertEqual(self._found('sunset'), set())

    def test_a_category_rename_reaches_the_next_search(self):
        self.assertEqual(self._found('water'), {self.kayak.pk})
        self.water.name = 'Paddling'
        self.water.save()
        self.assertEqual(self._found('water'), set())
        self.assertEqual(self._found('paddling'), {self.kayak.pk})

    def test_places_are_indexed(self):
        place = Place.objects.create(
            name='Perast', slug='perast', region='kotor', is_active=True, summary='s', description='d'
        )
        self.assertEqual(self._found('perast', kind='place'), {place.pk})
        self.assertEqual(self._found('perast'), set())

    def test_another_process_bump_rebuilds(self):
        search.listing_index()
        BookableService.objects.filter(pk=self.kayak.pk).update(name='Dawn Kayak Tour')
        self.assertEqual(self._found('dawn'), set())  # this process still has the old index
        cache.set(search._VERSION_KEY, 'set-by-another-process')
        self.assertEqual(self._found('dawn'), {self.kayak.pk})

    def test_a_lost_version_key_rebuilds(self):
        search.listing_index()
        BookableService.objects.filter(pk=self.kayak.pk).update(name='Dawn Kayak Tour')
        cache.delete(search._VERSION_KEY)
        self.assertEqual(self._found('dawn'), {self.kayak.pk})

    def test_an_edit_that_skips_save_is_found_once_the_index_ages_out(self):
        search.listing_index()
        BookableService.objects.filter(pk=self.kayak.pk).update(name='Dawn Kayak Tour')
        self.assertEqual(self._found('dawn'), set())
        version, built_at, index = search._STATE['built']
        search._STATE['built'] = (version, built_at - search.MAX_AGE_S - 1, index)
        self.assertEqual(self._found('dawn'), {self.kayak.pk})
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_index`
Expected: ERROR in every test, with `AttributeError: module 'plugins.installed.booking_marketplace.search' has no attribute 'listing_index'`.

- [ ] **Step 3: Add the store index**

In `search.py`, replace the import block

```python
import bisect
import re
import unicodedata
from typing import NamedTuple
```

with

```python
import bisect
import logging
import re
import time
import unicodedata
import uuid
from typing import NamedTuple

logger = logging.getLogger('morpheus.booking_marketplace')
```

and append to the end of `search.py`:

```python


# -- the store's index ---------------------------------------------------------
# Built once per process. `bump` (connected in app.py to every listing, place and category
# save or delete) writes a new version token to the shared cache, and a process holding an
# index built under another token rebuilds before its next search. An edit that skips
# save() — `QuerySet.update()` in the seed commands — is picked up once the index is
# MAX_AGE_S old. Callers filter by the database first and pass the survivors as `within`:
# the index ranks, it never decides what is live.
MAX_AGE_S = 600
_VERSION_KEY = 'booking_marketplace:search:version'
_STATE: dict = {}


def _flatten(value) -> str:
    """Highlights as text: strings, or the strings inside lists and dicts."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return ' '.join(_flatten(item) for item in value.values())
    if isinstance(value, list | tuple):
        return ' '.join(_flatten(item) for item in value)
    return ''


def _region_names() -> dict[str, str]:
    """Each region's label in English and in Serbian, so `boka` finds Kotor Bay."""
    from django.utils import translation

    from plugins.installed.booking_marketplace.models import REGIONS

    names = {}
    for key, label in REGIONS:
        spellings = []
        for language in ('en', 'sr'):
            with translation.override(language):
                spellings.append(str(label))
        names[key] = ' '.join(dict.fromkeys(spellings))
    return names


def documents() -> list[Doc]:
    """The active listings (both kinds) and places, as the index reads them."""
    from plugins.installed.booking_marketplace.models import BookableService, Place
    from plugins.installed.booking_marketplace.products import plain_text

    regions = _region_names()
    docs = [
        Doc(
            listing.pk,
            listing.listing_kind,
            (
                (10, listing.name),
                (6, listing.location),
                (6, regions.get(listing.region, '')),
                (5, listing.category.name if listing.category_id else ''),
                (3, _flatten(listing.highlights)),
                (2, plain_text(listing.short_description)),
                (1, plain_text(listing.description)),
            ),
        )
        for listing in BookableService.objects.filter(is_active=True).select_related('category')
    ]
    docs += [
        Doc(place.pk, 'place', ((10, place.name), (6, regions.get(place.region, ''))))
        for place in Place.objects.filter(is_active=True)
    ]
    return docs


def _version() -> str:
    from django.core.cache import cache

    try:
        current = cache.get(_VERSION_KEY)
        if current is None:
            cache.add(_VERSION_KEY, uuid.uuid4().hex, None)
            current = cache.get(_VERSION_KEY)
    except Exception:  # noqa: BLE001 — without the cache the index still ages out
        return ''
    return current or ''


def bump(**_kwargs) -> None:
    """post_save / post_delete: every process rebuilds its index before its next search."""
    from django.core.cache import cache

    try:
        cache.set(_VERSION_KEY, uuid.uuid4().hex, None)
    except Exception:  # noqa: BLE001 — a cache outage must never fail a listing save
        logger.warning('booking search: could not bump the index version', exc_info=True)


def listing_index() -> Index:
    """This process's index of the store, rebuilt first when it is stale."""
    version = _version()
    built = _STATE.get('built')
    if built is None or built[0] != version or time.monotonic() - built[1] > MAX_AGE_S:
        built = (version, time.monotonic(), Index(documents()))
        _STATE['built'] = built
    return built[2]
```

In `app.py` `ready()`, after the line `self.register_hook(events.STOREFRONT_SEARCH_PATH, booking_seo.on_search_path, priority=50)`, add:

```python

        # The search index rebuilds after a listing, a place or a category changes (search.py).
        from django.db.models.signals import post_delete, post_save

        from plugins.installed.booking_marketplace import search as booking_search
        from plugins.installed.booking_marketplace.models import BookableService, Place
        from plugins.installed.catalog.models import Category

        for model in (BookableService, Place, Category):
            uid = f'booking_search_{model._meta.label_lower}'
            post_save.connect(booking_search.bump, sender=model, dispatch_uid=uid)
            post_delete.connect(booking_search.bump, sender=model, dispatch_uid=uid)
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_index plugins.installed.booking_marketplace.tests.test_search_engine`
Expected: `Ran 26 tests` … `OK`.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check --fix plugins/installed/booking_marketplace/search.py plugins/installed/booking_marketplace/app.py plugins/installed/booking_marketplace/tests/test_search_index.py
.venv/bin/ruff format plugins/installed/booking_marketplace/search.py plugins/installed/booking_marketplace/app.py plugins/installed/booking_marketplace/tests/test_search_index.py
git add plugins/installed/booking_marketplace/search.py plugins/installed/booking_marketplace/app.py plugins/installed/booking_marketplace/tests/test_search_index.py
git commit -m "feat(booking): the search index follows listing, place and category changes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: A date keeps what can still be booked that day

**Files:**
- Modify: `plugins/installed/booking_marketplace/services.py` (`bookable_on`, after `available_sessions`)
- Test: `plugins/installed/booking_marketplace/tests/test_bookable_on.py`

**Interfaces:**
- Produces: `services.bookable_on(services, day) -> list`. It takes a QuerySet (whose windows it prefetches) or a list, and returns the bookable listings in the given order.

- [ ] **Step 1: Write the failing tests**

Create `plugins/installed/booking_marketplace/tests/test_bookable_on.py`:

```python
"""A date keeps the experiences a guest can still book that day (services.bookable_on).

The search bar sent `date=` and nothing read it. The rule is available_sessions' for
one day: the listing runs that weekday (no windows: every day) and a departure has a
seat left — capacity minus that day's pending and confirmed guests, per departure time
when it has times, for the whole day when it has none.
"""

from __future__ import annotations

import datetime

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import AvailabilityWindow, BookableService, Booking
from plugins.installed.booking_marketplace.services import available_sessions, bookable_on
from plugins.installed.catalog.models import Vendor


class BookableOnTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        self.day = timezone.localdate() + datetime.timedelta(days=3)
        weekday = self.day.weekday()

        self._listing('every-day')
        self._window(self._listing('another-weekday'), (weekday + 1) % 7)
        self._window(self._listing('that-weekday'), weekday)
        self._book(self._listing('full-day', capacity=2), guests=2)
        two = self._listing('one-departure-left', capacity=2)
        self._window(two, weekday, datetime.time(9, 0))
        self._window(two, weekday, datetime.time(14, 0))
        self._book(two, guests=2, slot='09:00')
        both = self._listing('both-departures-full', capacity=2)
        self._window(both, weekday, datetime.time(9, 0))
        self._window(both, weekday, datetime.time(14, 0))
        self._book(both, guests=2, slot='09:00')
        self._book(both, guests=2, slot='14:00')
        self._book(self._listing('cancelled-booking', capacity=2), guests=2, status='cancelled')

    def _listing(self, slug, capacity=4):
        return BookableService.objects.create(
            vendor=self.vendor, name=slug, slug=slug, price=Money(50, 'EUR'), daily_capacity=capacity
        )

    def _window(self, listing, weekday, start=None):
        AvailabilityWindow.objects.create(service=listing, weekday=weekday, start_time=start)

    def _book(self, listing, *, guests, slot='', status='confirmed'):
        Booking.objects.create(
            service=listing,
            customer_name='Guest',
            customer_email='guest@example.com',
            booking_date=self.day,
            time_slot=slot,
            guests=guests,
            status=status,
        )

    def test_the_rule(self):
        kept = [s.slug for s in bookable_on(BookableService.objects.order_by('slug'), self.day)]
        self.assertEqual(
            kept, ['cancelled-booking', 'every-day', 'one-departure-left', 'that-weekday']
        )

    def test_three_queries_whatever_the_number_of_listings(self):
        # the listings, their windows, and that day's bookings grouped by listing and departure
        with self.assertNumQueries(3):
            bookable_on(BookableService.objects.all(), self.day)

    def test_it_agrees_with_the_booking_widget(self):
        for listing in BookableService.objects.all():
            offered = any(s['date'] == self.day for s in available_sessions(listing, days=7))
            with self.subTest(listing=listing.slug):
                self.assertEqual(offered, listing in bookable_on([listing], self.day))

    def test_nothing_in_nothing_out(self):
        self.assertEqual(bookable_on(BookableService.objects.none(), self.day), [])
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_bookable_on`
Expected: ERROR, `ImportError: cannot import name 'bookable_on'`.

- [ ] **Step 3: Write `bookable_on`**

In `services.py`, add `from collections import defaultdict` to the imports (after `import datetime`). Then add, right after `available_sessions`:

```python
def bookable_on(services, day) -> list:
    """The listings in `services` a guest can still book on `day`, in the given order.

    `available_sessions`' rule for one date: the listing runs that weekday (no windows:
    every day) and a departure has a seat — its capacity minus that day's pending and
    confirmed guests on that departure, or on the whole day when it has no departure
    times. One query for the day's bookings; a QuerySet gets its windows prefetched.
    """
    from plugins.installed.booking_marketplace.models import Booking

    if hasattr(services, 'prefetch_related'):
        services = services.prefetch_related('availability')
    services = list(services)
    if not services:
        return []
    by_slot: dict = defaultdict(int)
    by_day: dict = defaultdict(int)
    rows = (
        Booking.objects.filter(
            service_id__in=[s.pk for s in services], booking_date=day, status__in=ACTIVE_STATUSES
        )
        .order_by()
        .values('service_id', 'time_slot')
        .annotate(guests_booked=Sum('guests'))
    )
    for row in rows:
        by_slot[(row['service_id'], row['time_slot'])] += row['guests_booked'] or 0
        by_day[row['service_id']] += row['guests_booked'] or 0
    kept = []
    for service in services:
        if day.weekday() not in _weekdays(service):
            continue
        capacity = service.daily_capacity or 0
        times = _start_times(service)
        if times == [None]:
            free = capacity - by_day[service.pk] > 0
        else:
            free = any(capacity - by_slot[(service.pk, slot)] > 0 for slot in times)
        if free:
            kept.append(service)
    return kept
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_bookable_on plugins.installed.booking_marketplace.tests.test_sessions`
Expected: `OK`. `test_sessions` runs too because `bookable_on` sits beside the session code it mirrors.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check --fix plugins/installed/booking_marketplace/services.py plugins/installed/booking_marketplace/tests/test_bookable_on.py
.venv/bin/ruff format plugins/installed/booking_marketplace/services.py plugins/installed/booking_marketplace/tests/test_bookable_on.py
git add plugins/installed/booking_marketplace/services.py plugins/installed/booking_marketplace/tests/test_bookable_on.py
git commit -m "feat(booking): a date keeps the experiences that still have a seat that day" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The lists answer the search

**Files:**
- Create: `plugins/installed/booking_marketplace/search_page.py`
- Modify: `plugins/installed/booking_marketplace/views.py`:
  - imports
  - the new helpers `_ORDER`, `_sort`, `_ranked` and `_searched`
  - `services_list` and `products_list`
- Modify: `locale/sr/LC_MESSAGES/django.po` and `.mo`
- Test: `plugins/installed/booking_marketplace/tests/test_search_results.py`

**Interfaces:**
- Consumes:
  - `search.parse_query` and `search.listing_index().find(...)` (Tasks 1–2)
  - `services.bookable_on` (Task 3)
- Produces, in `search_page`:
  - `SearchParams(q, region, region_label, day, date_note, category)`
  - `read_params(request)`
  - `date_locale() -> (babel, browser)`
  - `date_label(day) -> str`
  - `values(params) -> dict`, with keys `q region region_label date_iso date_label date_note category category_label`
  - `heading(params)` (the date, when set, joins the title), `chips(request, params)` and `empty_message(params, *, kind='experience')`
  - `page_context(request, params, *, close=False, kind='experience')`, which returns `values()` plus `heading chips clear_url close card_heading empty_message`
- Produces, in the views' context:
  - `services`
  - `q`
  - `region`
  - `category` (a slug, or `''`)
  - `sort` (`'best'` when there is a query)
  - `search` (the `page_context` dict)

- [ ] **Step 1: Write the failing tests**

Create `plugins/installed/booking_marketplace/tests/test_search_results.py`:

```python
"""The experiences and shop lists answer what the search bar asked (views + search_page).

Live on 2026-10-14 a multi-word search found nothing, the date was never read, the menu's
category links (`?category=water-sports`) showed 0 results, and results came in the
recommended order whatever was typed.
"""

from __future__ import annotations

import datetime
import types
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone, translation
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.booking_marketplace import search_page
from plugins.installed.booking_marketplace.models import BookableService, Booking
from plugins.installed.catalog.models import Category, Vendor

P = search_page.SearchParams
WATER = types.SimpleNamespace(name='Water Sports', slug='water-sports')
SUNDAY = datetime.date(2026, 10, 18)


class SearchFixture:
    def setUp(self):
        super().setUp()
        vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        self.water = Category.objects.create(name='Water Sports', slug='water-sports')
        culture = Category.objects.create(name='Culture', slug='culture')

        def listing(slug, name, *, location='', region='', category=culture, description='', kind='experience'):
            return BookableService.objects.create(
                vendor=vendor,
                slug=slug,
                name=name,
                location=location,
                region=region,
                category=category,
                description=description,
                listing_kind=kind,
                price=Money(50, 'EUR'),
                daily_capacity=4,
            )

        self.kotor_kayak = listing(
            'kotor-kayak', 'Sunset Kayak Tour on the Bay of Kotor', location='Kotor',
            region='kotor', category=self.water,
        )
        listing(
            'budva-kayak', 'Kayak and Snorkel Tour to Sveti Nikola Island', location='Budva',
            region='budva', category=self.water,
        )
        listing(
            'kotor-walk', 'Kotor Old Town Walk', location='Kotor', region='kotor',
            description='Ends at the kayak harbour.',
        )
        listing('zabljak-hike', 'Durmitor Day Hike', location='Žabljak', region='durmitor')
        listing('wild-honey', 'Wild Mountain Honey', kind='product')
        self.day = timezone.localdate() + datetime.timedelta(days=5)

    def _get(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response

    def _slugs(self, path):
        return [s.slug for s in self._get(path).context['services']]

    def _search(self, path):
        return self._get(path).context['search']


@override_settings(BOOKING_LISTING_MODE=False)
class ExperienceResultsTests(SearchFixture, TestCase):
    def test_every_word_in_any_order_best_match_first(self):
        self.assertEqual(self._slugs('/bookings/?q=kayak+kotor'), ['kotor-kayak', 'kotor-walk'])
        self.assertEqual(self._slugs('/bookings/?q=kotor+kayak'), ['kotor-kayak', 'kotor-walk'])

    def test_accents_serbian_and_typos(self):
        self.assertEqual(self._slugs('/bookings/?q=zabljak'), ['zabljak-hike'])
        kayaks = {'kotor-kayak', 'budva-kayak', 'kotor-walk'}
        self.assertEqual(set(self._slugs('/bookings/?q=kajak')), kayaks)
        self.assertEqual(set(self._slugs('/bookings/?q=kayac')), kayaks)

    def test_close_matches_when_no_listing_has_every_word(self):
        response = self._get('/bookings/?q=kayak+ulcinj')
        self.assertTrue(response.context['search']['close'])
        self.assertEqual(
            {s.slug for s in response.context['services']}, {'kotor-kayak', 'budva-kayak', 'kotor-walk'}
        )

    def test_close_matches_stay_inside_the_filters(self):
        self.assertEqual(self._slugs('/bookings/?q=kayak+ulcinj&region=budva'), ['budva-kayak'])

    def test_category_by_slug_or_name_in_any_case(self):
        for value in ('water-sports', 'Water+Sports', 'WATER-SPORTS', 'water+sports'):
            with self.subTest(value=value):
                self.assertEqual(
                    set(self._slugs(f'/bookings/?category={value}')), {'kotor-kayak', 'budva-kayak'}
                )
        self.assertEqual(self._get('/bookings/?category=Water+Sports').context['category'], 'water-sports')

    def test_an_unknown_category_or_region_is_ignored(self):
        self.assertEqual(len(self._slugs('/bookings/?category=nope')), 4)
        self.assertEqual(self._search('/bookings/?category=nope')['category'], '')
        self.assertEqual(len(self._slugs('/bookings/?region=narnia')), 4)
        self.assertEqual(self._search('/bookings/?region=narnia')['region'], '')

    def test_a_date_drops_what_is_full_that_day(self):
        Booking.objects.create(
            service=self.kotor_kayak, customer_name='A', customer_email='a@example.com',
            booking_date=self.day, guests=4, status='confirmed',
        )
        path = f'/bookings/?date={self.day.isoformat()}'
        self.assertEqual(
            set(self._slugs(path)), {'budva-kayak', 'kotor-walk', 'zabljak-hike'}
        )
        self.assertEqual(self._search(path)['date_iso'], self.day.isoformat())

    def test_a_past_date_is_ignored_with_a_note(self):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        response = self._get(f'/bookings/?date={yesterday.isoformat()}')
        self.assertEqual(len(response.context['services']), 4)
        self.assertEqual(response.context['search']['date_note'], 'Choose a date from today on')
        self.assertEqual(response.context['search']['date_iso'], '')

    def test_today_counts_and_nonsense_is_ignored(self):
        today = timezone.localdate().isoformat()
        self.assertEqual(self._search(f'/bookings/?date={today}')['date_iso'], today)
        nonsense = self._search('/bookings/?date=2026-13-45')
        self.assertEqual((nonsense['date_iso'], nonsense['date_note']), ('', ''))

    def test_everything_together(self):
        path = f'/bookings/?q=kayak&region=kotor&category=water-sports&date={self.day.isoformat()}'
        self.assertEqual(self._slugs(path), ['kotor-kayak'])

    def test_the_order(self):
        self.assertEqual(self._get('/bookings/?q=kayak').context['sort'], 'best')
        self.assertEqual(self._get('/bookings/').context['sort'], 'recommended')
        self.assertEqual(self._get('/bookings/?sort=best').context['sort'], 'recommended')
        self.assertEqual(self._get('/bookings/?q=kayak&sort=rating').context['sort'], 'rating')
        self.assertEqual(self._get('/bookings/?sort=nonsense').context['sort'], 'recommended')

    def test_a_huge_query_still_answers(self):
        response = self._get('/bookings/?q=' + 'kayak+' * 2000)
        self.assertLessEqual(len(response.context['q']), 200)

    def test_a_search_is_reported(self):
        with mock.patch.object(hook_registry, 'fire', wraps=hook_registry.fire) as fire:
            self._get('/bookings/?q=kayak+kotor')
            self._get('/bookings/?q=kayak+ulcinj')
            self._get('/bookings/?region=kotor')
        searches = [
            (call.kwargs['query'], call.kwargs['result_count'])
            for call in fire.call_args_list
            if call.args and call.args[0] == MorpheusEvents.SEARCH_PERFORMED
        ]
        self.assertEqual(searches, [('kayak kotor', 2), ('kayak ulcinj', 0)])


@override_settings(BOOKING_LISTING_MODE=False)
class ShopResultsTests(SearchFixture, TestCase):
    def test_the_shop_searches_its_goods(self):
        self.assertEqual(self._slugs('/shop/?q=honey'), ['wild-honey'])
        self.assertEqual(self._slugs('/shop/?q=med'), ['wild-honey'])
        self.assertEqual(self._slugs('/shop/?q=kayak'), [])
        self.assertEqual(len(self._slugs('/shop/')), 1)


class SearchWordsTests(SimpleTestCase):
    def test_headings(self):
        self.assertEqual(
            search_page.heading(P(q='kayak', region='kotor', region_label='Kotor Bay')),
            '“kayak” in Kotor Bay',
        )
        self.assertEqual(search_page.heading(P(q='kayak')), '“kayak” in Montenegro')
        self.assertEqual(search_page.heading(P(category=WATER)), 'Water Sports experiences in Montenegro')
        self.assertEqual(
            search_page.heading(P(category=WATER, region='budva', region_label='Budva Riviera')),
            'Water Sports experiences in Budva Riviera',
        )
        self.assertEqual(search_page.heading(P()), 'Experiences in Montenegro')
        self.assertEqual(
            search_page.heading(P(q='kayak', day=SUNDAY)), '“kayak” in Montenegro on Sun 18 Oct'
        )

    def test_the_empty_state(self):
        self.assertEqual(
            search_page.empty_message(P(q='zzz', day=SUNDAY)), 'No experiences match “zzz” on Sun 18 Oct'
        )
        self.assertEqual(search_page.empty_message(P(q='zzz')), 'No experiences match “zzz”')
        self.assertEqual(search_page.empty_message(P(day=SUNDAY)), 'Nothing left to book on Sun 18 Oct')
        self.assertEqual(search_page.empty_message(P()), 'No experiences match your search.')
        self.assertEqual(search_page.empty_message(P(q='x'), kind='product'), 'No products match “x”')

    def test_dates_are_latin_in_serbian(self):
        self.assertEqual(search_page.date_label(SUNDAY), 'Sun 18 Oct')
        self.assertEqual(search_page.date_label(None), '')
        with translation.override('sr'):
            self.assertEqual(search_page.date_label(SUNDAY), 'ned 18. okt')
            self.assertEqual(search_page.date_locale(), ('sr_Latn_ME', 'sr-Latn-ME'))

    def test_serbian_words(self):
        with translation.override('sr'):
            self.assertEqual(search_page.heading(P(q='kajak')), '„kajak“ u Crnoj Gori')
            self.assertEqual(
                search_page.heading(P(q='kajak', day=SUNDAY)), '„kajak“ u Crnoj Gori, ned 18. okt'
            )
            self.assertEqual(
                search_page.heading(P(q='kajak', region='kotor', region_label='Boka Kotorska')),
                '„kajak“ — Boka Kotorska',
            )
            self.assertEqual(
                search_page.empty_message(P(q='kajak')), 'Nijedan doživljaj ne odgovara upitu „kajak“'
            )
            self.assertEqual(
                search_page.empty_message(P(day=SUNDAY)), 'Za ned 18. okt nema slobodnih mjesta'
            )
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_results`
Expected: ERROR, `ImportError: cannot import name 'search_page'`.

- [ ] **Step 3: Write `search_page.py`**

Create `plugins/installed/booking_marketplace/search_page.py`:

```python
"""What a search on the travel store asks for, and how its page says so.

The list views and the search bar read the request through `read_params`, so the bar
always shows what the results were filtered by: a known region, a date from today on,
a live category named by its slug or its name. The page's heading, its filter chips and
its empty-state line are built here (docs/superpowers/specs/2026-10-14-montenegro-search-design.md).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _

# Django's own `sr` catalog names days and months in Cyrillic (суб., Окт.) on a store
# written in Latin. Babel and the browser's Intl both follow CLDR, so the server's label
# and search.js's agree.
_DATE_LOCALES = {'sr': ('sr_Latn_ME', 'sr-Latn-ME')}
_DEFAULT_DATE_LOCALE = ('en_GB', 'en-GB')
QUERY_MAX_CHARS = 200


@dataclass(frozen=True)
class SearchParams:
    """A search, validated: anything unknown or unusable is dropped, never echoed."""

    q: str = ''
    region: str = ''
    region_label: str = ''
    day: datetime.date | None = None
    date_note: str = ''
    category: object = None  # a catalog Category


def read_params(request) -> SearchParams:
    """The search in `request.GET`."""
    from plugins.installed.booking_marketplace.models import REGIONS

    get = request.GET
    labels = {key: str(label) for key, label in REGIONS}
    region = (get.get('region') or '').strip()
    if region not in labels:
        region = ''
    day, note = _day(get.get('date'))
    return SearchParams(
        q=(get.get('q') or '').strip()[:QUERY_MAX_CHARS],
        region=region,
        region_label=labels.get(region, ''),
        day=day,
        date_note=note,
        category=_category(get.get('category')),
    )


def _day(raw) -> tuple[datetime.date | None, str]:
    raw = (raw or '').strip()
    if not raw:
        return None, ''
    try:
        day = datetime.date.fromisoformat(raw)
    except ValueError:
        return None, ''
    if day < timezone.localdate():
        return None, _('Choose a date from today on')
    return day, ''


def _category(raw):
    """An active category named by its slug or its exact name, in any case."""
    from django.db.models import Q

    from plugins.installed.catalog.models import Category

    raw = (raw or '').strip()
    if not raw:
        return None
    return Category.objects.filter(Q(slug__iexact=raw) | Q(name__iexact=raw), is_active=True).first()


def date_locale() -> tuple[str, str]:
    """(Babel, browser) locale for dates in the visitor's language."""
    return _DATE_LOCALES.get((get_language() or 'en').split('-')[0], _DEFAULT_DATE_LOCALE)


def date_label(day) -> str:
    """'Sun 18 Oct' or 'ned 18. okt'; '' without a date."""
    if day is None:
        return ''
    try:
        from babel.dates import format_skeleton

        return format_skeleton('MMMEd', day, locale=date_locale()[0])
    except Exception:  # noqa: BLE001 — Babel arrives with py-moneyed; a label never fails a page
        return day.isoformat()


def values(params: SearchParams) -> dict:
    """What the search bar shows of a search."""
    category = params.category
    return {
        'q': params.q,
        'region': params.region,
        'region_label': params.region_label,
        'date_iso': params.day.isoformat() if params.day else '',
        'date_label': date_label(params.day),
        'date_note': params.date_note,
        'category': category.slug if category is not None else '',
        'category_label': category.name if category is not None else '',
    }


def heading(params: SearchParams) -> str:
    """The results page's h1: the query, else the category, else the plain title; then the date."""
    title = _title(params)
    if params.day:
        return _('%(title)s on %(date)s') % {'title': title, 'date': date_label(params.day)}
    return title


def _title(params: SearchParams) -> str:
    if params.q:
        if params.region_label:
            return _('“%(q)s” in %(region)s') % {'q': params.q, 'region': params.region_label}
        return _('“%(q)s” in Montenegro') % {'q': params.q}
    if params.category is not None:
        name = params.category.name
        if params.region_label:
            return _('%(category)s experiences in %(region)s') % {
                'category': name,
                'region': params.region_label,
            }
        return _('%(category)s experiences in Montenegro') % {'category': name}
    return _('Experiences in Montenegro')


def chips(request, params: SearchParams) -> list[dict]:
    """One removable chip per filter in force; its link is this page without it."""
    shown = []
    if params.q:
        shown.append(('q', _('“%(q)s”') % {'q': params.q}))
    if params.region:
        shown.append(('region', params.region_label))
    if params.day:
        shown.append(('date', date_label(params.day)))
    if params.category is not None:
        shown.append(('category', params.category.name))
    return [{'param': p, 'label': label, 'href': _without(request, p)} for p, label in shown]


def _without(request, param: str) -> str:
    query = request.GET.copy()
    for key in (param, 'page'):
        query.pop(key, None)
    encoded = query.urlencode()
    return f'{request.path}?{encoded}' if encoded else request.path


def empty_message(params: SearchParams, *, kind: str = 'experience') -> str:
    """What the page says when nothing matches every word, or nothing at all."""
    if kind == 'product':
        if params.q:
            return _('No products match “%(q)s”') % {'q': params.q}
        return _('No products match your search.')
    when = date_label(params.day)
    if params.q and when:
        return _('No experiences match “%(q)s” on %(date)s') % {'q': params.q, 'date': when}
    if params.q:
        return _('No experiences match “%(q)s”') % {'q': params.q}
    if when:
        return _('Nothing left to book on %(date)s') % {'date': when}
    return _('No experiences match your search.')


def page_context(request, params: SearchParams, *, close=False, kind='experience') -> dict:
    """The `search` a results page renders (list.html) and its search bar reads."""
    return {
        **values(params),
        'heading': heading(params),
        'chips': chips(request, params),
        'clear_url': request.path,
        'close': close,
        'card_heading': 'h3' if close else 'h2',
        'empty_message': empty_message(params, kind=kind),
    }
```


- [ ] **Step 4: Wire the views**

In `views.py`:

1. Add `import contextlib` after `import calendar`.
2. Add `from morpheus.core import MorpheusEvents, hook_registry` after the `core.utils.pagination` import.
3. Change `from plugins.installed.booking_marketplace import seo_jsonld` to `from plugins.installed.booking_marketplace import search, search_page, seo_jsonld`.
4. Add `bookable_on,` to the `services` import list, after `available_sessions,`.

Then replace the whole `services_list` and `products_list` functions (from `def services_list(request):` down to the `return render(...)` that closes `products_list`) with:

```python
# The orders a visitor can pick; "best" (the search's own score) joins them while there is a query.
_ORDER = {
    'recommended': ('-is_bestseller', '-rating', '-review_count'),
    'rating': ('-rating', '-review_count'),
    'price_low': ('price',),
    'price_high': ('-price',),
    'newest': ('-id',),
}


def _sort(request, *, has_query: bool) -> str:
    sort = (request.GET.get('sort') or '').strip()
    if sort in _ORDER or (sort == 'best' and has_query):
        return sort
    return 'best' if has_query else 'recommended'


def _ranked(rows, matches, sort: str) -> list:
    """`rows` the search matched; best first, top picks then names breaking ties, when asked."""
    rows = [row for row in rows if row.pk in matches.scores]
    if sort == 'best':
        rows.sort(
            key=lambda row: (-matches.scores[row.pk], not row.is_bestseller, row.name.casefold())
        )
    return rows


def _searched(request, q: str, count: int) -> None:
    """SEARCH_PERFORMED, as the storefront's own search fires it: search trends, the
    zero-result report and the GA4 search event read it. Close matches count as none."""
    with contextlib.suppress(Exception):
        hook_registry.fire(
            MorpheusEvents.SEARCH_PERFORMED, query=q, result_count=count, request=request
        )


def services_list(request):
    """Browse bookable experiences: what the search bar asked for, best match first."""
    from plugins.installed.catalog.category_tree import subtree_ids

    params = search_page.read_params(request)
    services = BookableService.objects.filter(
        is_active=True, vendor__is_active=True, listing_kind='experience'
    ).select_related('vendor', 'category')
    if params.region:
        services = services.filter(region=params.region)
    if params.category is not None:
        services = services.filter(category_id__in=subtree_ids([params.category]))
    terms = search.parse_query(params.q)
    sort = _sort(request, has_query=bool(terms))
    services = services.order_by(*_ORDER.get(sort, _ORDER['recommended']))
    rows = bookable_on(services, params.day) if params.day else list(services)
    matches = None
    if terms:
        matches = search.listing_index().find(
            terms, kind='experience', within={row.pk for row in rows}
        )
        rows = _ranked(rows, matches, sort)
        _searched(request, params.q, 0 if matches.close else len(rows))
    # 142 experiences on one page was a 381 KB document; 48 is four rows of
    # the grid. A page past the end is a 404, like every other listing.
    page_obj = paginate_or_404(rows, 48, request)
    # The title names a category only when the filter matched a real one: it used to
    # echo whatever `?category=` held, one indexable title per string anyone typed.
    label = params.category.name if params.category is not None else ''
    seo_title = (
        _('%(category)s experiences in Montenegro') % {'category': label}
        if label
        else _('Experiences in Montenegro — book with local hosts')
    )
    seo_description = (
        _(
            'Book %(category)s experiences in Montenegro with trusted local hosts '
            '— instant confirmation, free cancellation on most tours.'
        )
        % {'category': label}
        if label
        else _('Tours, activities and rentals from trusted local hosts across the Adriatic.')
    )
    services = list(page_obj.object_list)
    return render(
        request,
        'booking_marketplace/list.html',
        {
            'services': services,
            'listing_mode': listing_mode(),
            'region': params.region,
            'q': params.q,
            'category': params.category.slug if params.category is not None else '',
            'sort': sort,
            'search': search_page.page_context(
                request, params, close=bool(matches and matches.close)
            ),
            'seo_title': seo_title,
            'seo_description': seo_description,
            'breadcrumb_items': _crumbs(request, (_('Experiences'), '/bookings/')),
            'jsonld_items': seo_jsonld.listing_items(
                [(s.name, f'/bookings/{s.slug}/', _image_url(s)) for s in services[:60]],
                request=request,
            ),
            'page_obj': page_obj,
            # Zero results (an empty region or category filter) is held out of
            # the index; a `?q=` search is search results whatever it finds.
            'seo_item_count': page_obj.paginator.count,
        },
    )


def products_list(request):
    """Browse product-kind listings (the Shop); a search shows its best matches first."""
    q = (request.GET.get('q') or '').strip()[: search_page.QUERY_MAX_CHARS]
    products = list(
        BookableService.objects.filter(
            is_active=True, vendor__is_active=True, listing_kind='product'
        )
        .select_related('vendor', 'category')
        .order_by('-is_bestseller', 'name')
    )
    terms = search.parse_query(q)
    matches = None
    if terms:
        matches = search.listing_index().find(
            terms, kind='product', within={p.pk for p in products}
        )
        products = _ranked(products, matches, 'best')
        _searched(request, q, 0 if matches.close else len(products))
    return render(
        request,
        'booking_marketplace/list.html',
        {
            'services': products,
            'listing_mode': listing_mode(),
            'is_product_shop': True,
            'q': q,
            'search': search_page.page_context(
                request,
                search_page.SearchParams(q=q),
                close=bool(matches and matches.close),
                kind='product',
            ),
            'seo_title': _('Shop Montenegro — local goods'),
            'seo_description': _(
                'Locally made Montenegrin products from trusted vendors — shipped '
                'or ready for pickup across the Adriatic coast.'
            ),
            'breadcrumb_items': _crumbs(request, (_('Shop'), '/shop/')),
            'jsonld_items': seo_jsonld.listing_items(
                [(p.name, f'/bookings/{p.slug}/', _image_url(p)) for p in products[:60]],
                request=request,
            ),
            'seo_item_count': len(products),
        },
    )
```

- [ ] **Step 5: Serbian for the new strings**

Append to `locale/sr/LC_MESSAGES/django.po`. Each msgid was checked absent: re-check with `grep -nF` before appending.

```po

msgid "Choose a date from today on"
msgstr "Izaberite datum od danas nadalje"

#, python-format
msgid "“%(q)s” in Montenegro"
msgstr "„%(q)s“ u Crnoj Gori"

#, python-format
msgid "“%(q)s” in %(region)s"
msgstr "„%(q)s“ — %(region)s"

#, python-format
msgid "%(category)s experiences in %(region)s"
msgstr "%(category)s doživljaji — %(region)s"

#, python-format
msgid "“%(q)s”"
msgstr "„%(q)s“"

#, python-format
msgid "No experiences match “%(q)s” on %(date)s"
msgstr "Nijedan doživljaj ne odgovara upitu „%(q)s“ za %(date)s"

#, python-format
msgid "No experiences match “%(q)s”"
msgstr "Nijedan doživljaj ne odgovara upitu „%(q)s“"

#, python-format
msgid "Nothing left to book on %(date)s"
msgstr "Za %(date)s nema slobodnih mjesta"

#, python-format
msgid "No products match “%(q)s”"
msgstr "Nijedan proizvod ne odgovara upitu „%(q)s“"

#, python-format
msgid "%(title)s on %(date)s"
msgstr "%(title)s, %(date)s"
```

Compile: `msgfmt --check-format -o locale/sr/LC_MESSAGES/django.mo locale/sr/LC_MESSAGES/django.po`
Expected: no output, exit 0.

- [ ] **Step 6: Run the tests to see them pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_results plugins.installed.booking_marketplace.tests.test_booking plugins.installed.booking_marketplace.tests.test_seo_integration plugins.installed.booking_marketplace.tests.test_seo_meta plugins.installed.booking_marketplace.tests.test_experience_card_titles`
Expected: `OK`. The older suites check that the default list, `?q=kayak`, `?category=Adventure` (by name) and the region pages still behave.

- [ ] **Step 7: Lint and commit**

```bash
files=(plugins/installed/booking_marketplace/search_page.py plugins/installed/booking_marketplace/views.py plugins/installed/booking_marketplace/tests/test_search_results.py)
.venv/bin/ruff check --fix "${files[@]}" && .venv/bin/ruff format "${files[@]}"
git add "${files[@]}" locale/sr/LC_MESSAGES/django.po locale/sr/LC_MESSAGES/django.mo
git commit -m "feat(booking): the experiences and shop lists rank by the search, read the date and accept category slugs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Suggestions as you type

**Files:**
- Modify: `plugins/installed/booking_marketplace/search_page.py` (import `localized_path`; `suggestions` and its three helpers)
- Modify: `plugins/installed/booking_marketplace/services.py` (`active_categories` rows gain `slug`)
- Modify: `plugins/installed/booking_marketplace/views.py` (`suggest`)
- Modify: `plugins/installed/booking_marketplace/urls.py` (`bookings/suggest/`)
- Modify: `plugins/installed/analytics/middleware.py` (a pageview is an HTML page)
- Test: `plugins/installed/booking_marketplace/tests/test_search_suggest.py`
- Test: `plugins/installed/analytics/tests/test_pageviews_are_pages.py`

**Interfaces:**
- Consumes: `search.listing_index()`, `search.parse_query()`, `search.Index`, `search.Doc` (Tasks 1–2).
- Produces:
  - `GET /bookings/suggest/?q=` (URL name `booking_marketplace:suggest`) → JSON `{"experiences": [{name, url, location, image, price}], "places": [{name, url}], "categories": [{name, url, count}]}`, at most 5 experiences, 3 places and 3 categories.
  - `X-Robots-Tag: noindex` and `Cache-Control: public, max-age=60`.
  - `services.active_categories()` rows are now `{'name', 'slug', 'count'}`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/installed/booking_marketplace/tests/test_search_suggest.py`:

```python
"""Suggestions while a visitor types (GET /bookings/suggest/?q=…, read by search.js).

Every word must match: a suggestion is what was typed, never a close match. Links follow
the visitor's language, and the text is data the script sets with textContent.
"""

from __future__ import annotations

from django.test import TestCase, override_settings
from django.utils.text import slugify
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService, Place
from plugins.installed.booking_marketplace.tests._i18n import serbian_enabled
from plugins.installed.catalog.models import Category, Vendor

EMPTY = {'experiences': [], 'places': [], 'categories': []}


class SuggestFixture:
    def setUp(self):
        super().setUp()
        self.vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        categories = [
            Category.objects.create(name=f'Kotor {name}', slug=f'kotor-{name.lower()}')
            for name in ('Boats', 'Food', 'Walks', 'Wine')
        ]
        for i in range(6):
            BookableService.objects.create(
                vendor=self.vendor,
                name=f'Kotor Experience {i}',
                slug=f'kotor-experience-{i}',
                location='Kotor',
                region='kotor',
                category=categories[i % 4],
                price=Money(40 + i, 'EUR'),
            )
        for name in ('Kotor', 'Kotor Old Town', 'Kotor Fortress', 'Kotor Serpentine'):
            Place.objects.create(
                name=name, slug=slugify(name), region='kotor', is_active=True,
                summary='s', description='d',
            )

    def _json(self, q, path='/bookings/suggest/'):
        response = self.client.get(path, {'q': q})
        self.assertEqual(response.status_code, 200)
        return response.json()


@override_settings(BOOKING_LISTING_MODE=False)
class SuggestTests(SuggestFixture, TestCase):
    def test_the_shape_and_the_limits(self):
        data = self._json('kotor')
        self.assertEqual(set(data), {'experiences', 'places', 'categories'})
        self.assertEqual([len(data[k]) for k in ('experiences', 'places', 'categories')], [5, 3, 3])
        experience = data['experiences'][0]
        self.assertEqual(set(experience), {'name', 'url', 'location', 'image', 'price'})
        self.assertTrue(experience['url'].startswith('/bookings/kotor-experience-'))
        self.assertEqual(experience['location'], 'Kotor')
        self.assertIn('€', experience['price'])
        self.assertEqual(set(data['places'][0]), {'name', 'url'})
        self.assertEqual(data['places'][0], {'name': 'Kotor', 'url': '/places/kotor/'})
        self.assertEqual(set(data['categories'][0]), {'name', 'url', 'count'})
        self.assertEqual(data['categories'][0]['url'], '/bookings/?category=kotor-boats')
        self.assertEqual(data['categories'][0]['count'], 2)

    def test_too_short_or_too_long_answers_empty(self):
        self.assertEqual(self._json('k'), EMPTY)
        self.assertEqual(self._json(''), EMPTY)
        self.assertEqual(self._json('k' * 81), EMPTY)
        self.assertEqual(self._json('the'), EMPTY)  # only a stopword

    def test_it_is_never_indexed_and_briefly_cached(self):
        response = self.client.get('/bookings/suggest/', {'q': 'kotor'})
        self.assertEqual(response['X-Robots-Tag'], 'noindex')
        self.assertIn('public', response['Cache-Control'])
        self.assertIn('max-age=60', response['Cache-Control'])

    def test_only_live_experiences(self):
        hidden_host = Vendor.objects.create(name='Gone', slug='gone', is_active=False)
        BookableService.objects.create(
            vendor=hidden_host, name='Hidden Lagoon Tour', slug='hidden-lagoon', price=Money(1, 'EUR')
        )
        BookableService.objects.create(
            vendor=self.vendor, name='Hidden Cove Map', slug='hidden-map', listing_kind='product',
            price=Money(1, 'EUR'),
        )
        BookableService.objects.create(
            vendor=self.vendor, name='Hidden Beach Day', slug='hidden-beach', is_active=False,
            price=Money(1, 'EUR'),
        )
        self.assertEqual(self._json('hidden')['experiences'], [])

    def test_only_what_matches_every_word(self):
        self.assertEqual(self._json('kotor zzzz'), EMPTY)

    def test_text_is_data(self):
        BookableService.objects.create(
            vendor=self.vendor, name='<img src=x onerror=alert(1)> Cove', slug='cove',
            price=Money(1, 'EUR'),
        )
        self.assertEqual(
            [e['name'] for e in self._json('cove')['experiences']], ['<img src=x onerror=alert(1)> Cove']
        )

    @override_settings(BOOKING_LISTING_MODE=True)
    def test_listing_mode_shows_no_price(self):
        self.assertEqual({e['price'] for e in self._json('kotor')['experiences']}, {''})


@serbian_enabled
@override_settings(BOOKING_LISTING_MODE=False)
class SerbianSuggestTests(SuggestFixture, TestCase):
    def test_links_stay_in_serbian(self):
        data = self._json('kotor', path='/sr/bookings/suggest/')
        links = [item['url'] for group in data.values() for item in group]
        self.assertTrue(links)
        for link in links:
            with self.subTest(link=link):
                self.assertTrue(link.startswith('/sr/'), link)
```

Create `plugins/installed/analytics/tests/test_pageviews_are_pages.py`:

```python
"""A pageview is a page: a script's JSON fetch is not one.

The travel store's search bar asks /bookings/suggest/ for suggestions as a visitor
types, and every storefront GET was recorded as a pageview whatever it returned; the
cookie banner's /csrf/ fetch already was.
"""

from __future__ import annotations

from django.test import Client, TestCase

from plugins.installed.analytics.models import AnalyticsEvent

_BROWSER = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Version/17.5 Safari/605.1.15'
)


class PageviewsArePagesTests(TestCase):
    def _pageviews(self):
        return AnalyticsEvent.objects.filter(kind='pageview').count()

    def test_a_json_fetch_is_not_a_pageview(self):
        before = self._pageviews()
        response = Client(HTTP_USER_AGENT=_BROWSER).get('/csrf/')
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        self.assertEqual(self._pageviews(), before)

    def test_a_page_still_is(self):
        before = self._pageviews()
        Client(HTTP_USER_AGENT=_BROWSER).get('/')
        self.assertEqual(self._pageviews(), before + 1)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_suggest plugins.installed.analytics.tests.test_pageviews_are_pages`
Expected:
- The suggest tests fail with 404s, because `/bookings/suggest/` resolves to the listing detail with slug "suggest".
- `test_a_json_fetch_is_not_a_pageview` FAILS with `before + 1 != before`.
- `test_a_page_still_is` passes.

- [ ] **Step 3: Write the endpoint**

`services.py`: in `active_categories`, return the slug too, and update the docstring's list of readers:

```python
        return [{'name': c.name, 'slug': c.slug, 'count': c.svc_count} for c in rows]
```

and in its docstring replace `(home band, hero pills, filter chips, nav mega-menu)` with `(home band, search bar, results page, nav mega-menu)`.

`search_page.py`: add the import `from core.utils.i18n import localized_path` after the `django.utils.translation` imports, then append:

```python


def suggestions(request, q: str) -> dict:
    """Up to 5 experiences, 3 places and 3 categories matching every word of `q`.

    Never close matches: a suggestion is what was typed. Links follow the visitor's
    language, and nothing here is HTML — search.js sets every value as text.
    """
    from plugins.installed.booking_marketplace import search

    out = {'experiences': [], 'places': [], 'categories': []}
    terms = search.parse_query(q)
    if terms:
        index = search.listing_index()
        out['experiences'] = _suggested_experiences(request, index, terms)
        out['places'] = _suggested_places(request, index, terms)
        out['categories'] = _suggested_categories(request, terms)
    return out


def _suggested_experiences(request, index, terms) -> list[dict]:
    from core.templatetags.morph import money_filter
    from plugins.installed.booking_marketplace.models import REGIONS, BookableService
    from plugins.installed.booking_marketplace.views import _image_url, listing_mode

    live = BookableService.objects.filter(
        is_active=True, vendor__is_active=True, listing_kind='experience'
    )
    found = index.find(
        terms, kind='experience', within=set(live.values_list('pk', flat=True)), fallback=False
    )
    if not found.scores:
        return []
    rows = sorted(
        live.filter(pk__in=found.scores),
        key=lambda s: (-found.scores[s.pk], not s.is_bestseller, s.name.casefold()),
    )[:5]
    regions = {key: str(label) for key, label in REGIONS}
    hide_price = listing_mode()
    return [
        {
            'name': s.name,
            'url': localized_path(request, f'/bookings/{s.slug}/'),
            'location': s.location or regions.get(s.region, ''),
            'image': _image_url(s),
            'price': '' if hide_price else money_filter(s.price),
        }
        for s in rows
    ]


def _suggested_places(request, index, terms) -> list[dict]:
    from plugins.installed.booking_marketplace.models import Place

    places = Place.objects.filter(is_active=True)
    found = index.find(
        terms, kind='place', within=set(places.values_list('pk', flat=True)), fallback=False
    )
    if not found.scores:
        return []
    rows = sorted(
        places.filter(pk__in=found.scores), key=lambda p: (-found.scores[p.pk], p.name.casefold())
    )[:3]
    return [{'name': p.name, 'url': localized_path(request, f'/places/{p.slug}/')} for p in rows]


def _suggested_categories(request, terms) -> list[dict]:
    from plugins.installed.booking_marketplace import search
    from plugins.installed.booking_marketplace.services import active_categories

    categories = active_categories()
    found = search.Index(
        search.Doc(c['slug'], 'category', ((10, c['name']),)) for c in categories
    ).find(terms, kind='category', fallback=False)
    rows = sorted(
        (c for c in categories if c['slug'] in found.scores),
        key=lambda c: (-found.scores[c['slug']], -c['count'], c['name']),
    )[:3]
    return [
        {
            'name': c['name'],
            'url': localized_path(request, f'/bookings/?category={c["slug"]}'),
            'count': c['count'],
        }
        for c in rows
    ]
```

`views.py`: add after `products_list`:

```python
def suggest(request):
    """Suggestions while a visitor types in the search bar: JSON for search.js, never indexed."""
    from django.http import JsonResponse
    from django.utils.cache import patch_cache_control

    q = (request.GET.get('q') or '').strip()
    if 2 <= len(q) <= 80:
        payload = search_page.suggestions(request, q)
    else:
        payload = {'experiences': [], 'places': [], 'categories': []}
    response = JsonResponse(payload)
    response['X-Robots-Tag'] = 'noindex'
    patch_cache_control(response, public=True, max_age=60)
    return response
```

`urls.py`: right after `path('bookings/', views.services_list, name='list'),` add:

```python
    # Before the <slug> detail route below, or "suggest" reads as a listing's slug.
    path('bookings/suggest/', views.suggest, name='suggest'),
```

`plugins/installed/analytics/middleware.py`: in `AnalyticsMiddleware.__call__`, right after

```python
        if request.method != 'GET':
            return response
```

add

```python
        # A pageview is a page. A script's JSON fetch (the travel store's search
        # suggestions, the cookie banner's /csrf/) was recorded as one per request.
        if not (response.get('Content-Type') or '').startswith('text/html'):
            return response
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_suggest plugins.installed.analytics plugins.installed.booking_marketplace.tests.test_nav_derived`
Expected: `OK`. The whole analytics suite runs, so a test that relied on a non-HTML pageview would show here.

- [ ] **Step 5: Lint and commit**

```bash
files=(plugins/installed/booking_marketplace/search_page.py plugins/installed/booking_marketplace/services.py plugins/installed/booking_marketplace/views.py plugins/installed/booking_marketplace/urls.py plugins/installed/booking_marketplace/tests/test_search_suggest.py plugins/installed/analytics/middleware.py plugins/installed/analytics/tests/test_pageviews_are_pages.py)
.venv/bin/ruff check --fix "${files[@]}" && .venv/bin/ruff format "${files[@]}"
git add "${files[@]}"
git commit -m "feat(booking): suggestions as you type; analytics counts only pages as pageviews" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: One search bar

**Files:**
- Create: `themes/library/montenegro/templates/booking_marketplace/_search.html`
- Create: `themes/library/montenegro/static/montenegro/search.js`
- Delete: `themes/library/montenegro/templates/booking_marketplace/_search_bar.html`
- Modify: `themes/library/montenegro/templates/booking_marketplace/list.html`. Only the include line changes; Task 7 does the rest.
- Modify: `themes/library/montenegro/static/montenegro/refresh.css` (the search-bar section)
- Modify: `plugins/installed/booking_marketplace/services.py` (`live_regions`)
- Modify: `plugins/installed/booking_marketplace/search_page.py` (`bar_context`)
- Modify: `plugins/installed/booking_marketplace/templatetags/booking_tags.py` (`search_bar`)
- Modify: `locale/sr/LC_MESSAGES/django.po` and `.mo`
- Test: `plugins/installed/booking_marketplace/tests/test_search_bar.py`

**Interfaces:**
- Consumes:
  - `search_page.values`, `read_params`, `date_locale` (Task 4)
  - the suggest URL (Task 5)
  - `active_categories()` rows with `slug` (Task 5)
- Produces:
  - `services.live_regions() -> [{'key', 'label', 'count'}]`
  - `search_page.bar_context(request, variant, search=None) -> dict`
  - the `{% search_bar variant as sb %}` tag
  - `{% include "booking_marketplace/_search.html" with variant="hero"|"bar"|"shop" %}`, whose wrapper carries `data-mx-search="<variant>"`
  - element ids `sb-form-<variant>`, `sb-q-<variant>`, `sb-where-<variant>`, `sb-date-<variant>`, `sb-category-<variant>` and `sb-list-<variant>`

- [ ] **Step 1: Write the failing tests**

Create `plugins/installed/booking_marketplace/tests/test_search_bar.py`:

```python
"""One search bar for the travel store (booking_marketplace/_search.html).

The home hero and /bookings/ carried two copies of one form and /shop/ had none, the
labels were tied to no field, Where listed regions with nothing to book, and the date
field read "dd. mm. yyyy.".
"""

from __future__ import annotations

import datetime
import re
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.test import TestCase, override_settings
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace import search_page
from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.tests._i18n import serbian_enabled
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Category, Vendor

SCRIPT = (
    Path(settings.BASE_DIR) / 'themes' / 'library' / 'montenegro' / 'static' / 'montenegro' / 'search.js'
)
_BAR = re.compile(r'<div class="mx-sb mx-sb--(?P<variant>\w+)"[^>]*data-mx-search=.*?</form>', re.S)


def bars(body):
    return [(match.group('variant'), match.group(0)) for match in _BAR.finditer(body)]


class _Controls(HTMLParser):
    """The bar's fields and the ids its labels point at."""

    def __init__(self):
        super().__init__()
        self.fields, self.labelled = [], set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'label' and attrs.get('for'):
            self.labelled.add(attrs['for'])
        if tag in ('input', 'select') and attrs.get('type') not in ('hidden', 'submit', 'button'):
            self.fields.append(attrs.get('id'))


class BarFixture(MontenegroThemeMixin):
    def setUp(self):
        super().setUp()
        vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        water = Category.objects.create(name='Water Sports', slug='water-sports')
        for slug, region in (('kotor-a', 'kotor'), ('kotor-b', 'kotor'), ('budva-a', 'budva')):
            BookableService.objects.create(
                vendor=vendor, name=slug, slug=slug, region=region, category=water,
                price=Money(50, 'EUR'),
            )
        BookableService.objects.create(
            vendor=vendor, name='Honey', slug='honey', region='skadar', listing_kind='product',
            price=Money(9, 'EUR'),
        )
        self.day = timezone.localdate() + datetime.timedelta(days=4)

    def _body(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode()

    def _bar(self, path):
        (found,) = bars(self._body(path))
        return found[1]


@override_settings(BOOKING_LISTING_MODE=False)
class SearchBarTests(BarFixture, TestCase):
    def test_one_bar_on_the_listings_and_the_shop(self):
        self.assertEqual([variant for variant, _ in bars(self._body('/bookings/'))], ['bar'])
        self.assertEqual([variant for variant, _ in bars(self._body('/shop/'))], ['shop'])

    def test_the_old_partial_is_gone(self):
        with self.assertRaises(TemplateDoesNotExist):
            get_template('booking_marketplace/_search_bar.html')

    def test_every_field_has_a_label(self):
        for path in ('/bookings/', '/shop/'):
            controls = _Controls()
            controls.feed(self._bar(path))
            with self.subTest(path=path):
                self.assertTrue(controls.fields)
                self.assertTrue(all(controls.fields), 'a field without an id')
                self.assertLessEqual(set(controls.fields), controls.labelled)

    def test_where_lists_regions_with_live_experiences(self):
        bar = self._bar('/bookings/')
        where = re.search(r'<select[^>]*name="region".*?</select>', bar, re.S).group(0)
        self.assertEqual(re.findall(r'<option value="(\w*)"', where), ['', 'kotor', 'budva'])
        self.assertIn('Kotor Bay (2)', where)
        self.assertIn('Budva Riviera (1)', where)

    def test_categories_by_slug_and_selected_from_a_name(self):
        self.assertRegex(
            self._bar('/bookings/?category=Water+Sports'), r'<option value="water-sports" selected>'
        )

    def test_the_bar_shows_the_search(self):
        bar = self._bar(f'/bookings/?q=kayak&region=kotor&date={self.day.isoformat()}')
        self.assertIn('value="kayak"', bar)
        self.assertRegex(bar, r'<option value="kotor" selected>')
        self.assertIn(f'value="{self.day.isoformat()}"', bar)
        self.assertIn(search_page.date_label(self.day), bar)
        self.assertIn(f'min="{timezone.localdate().isoformat()}"', bar)

    def test_the_shop_bar_searches_goods(self):
        bar = self._bar('/shop/')
        self.assertIn('action="/shop/"', bar)
        self.assertNotIn('name="region"', bar)
        self.assertNotIn('data-suggest-url', bar)

    def test_the_listings_bar_asks_for_suggestions(self):
        bar = self._bar('/bookings/')
        self.assertIn('data-suggest-url="/bookings/suggest/"', bar)
        self.assertIn('role="combobox"', bar)
        self.assertIn('aria-controls="sb-list-bar"', bar)

    def test_the_script_is_deferred(self):
        self.assertRegex(
            self._body('/bookings/'), r'<script src="[^"]*montenegro/search(\.[0-9a-f]+)?\.js" defer>'
        )

    def test_the_script_never_writes_html(self):
        source = SCRIPT.read_text()
        for sink in ('innerHTML', 'outerHTML', 'insertAdjacentHTML', 'document.write'):
            with self.subTest(sink=sink):
                self.assertNotIn(sink, source)
        self.assertIn('textContent', source)


@serbian_enabled
@override_settings(BOOKING_LISTING_MODE=False)
class SerbianSearchBarTests(BarFixture, TestCase):
    def test_the_bar_follows_the_language(self):
        bar = self._bar(f'/sr/bookings/?date={self.day.isoformat()}')
        self.assertIn('data-suggest-url="/sr/bookings/suggest/"', bar)
        self.assertIn('data-date-locale="sr-Latn-ME"', bar)
        self.assertIn('action="/sr/bookings/"', bar)
        self.assertIsNone(re.search('[Ѐ-ӿ]', bar), 'Cyrillic in the Serbian search bar')
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_bar`
Expected: FAIL/ERROR across the board. `bars()` finds no `mx-sb` wrapper (so `(found,) = ...` raises ValueError), `_search_bar.html` still exists, and `search.js` does not (FileNotFoundError).

- [ ] **Step 3: The bar's data**

`services.py`, after `active_categories`:

```python
def live_regions() -> list[dict]:
    """Regions with a live experience, in REGIONS order, with counts: the search bar's Where.

    Fails soft to [] like active_categories(): the bar renders on the home page.
    """
    try:
        from plugins.installed.booking_marketplace.models import REGIONS, BookableService

        counts = dict(
            BookableService.objects.filter(
                is_active=True, vendor__is_active=True, listing_kind='experience'
            )
            .exclude(region='')
            .values_list('region')
            .annotate(n=Count('id'))
            .values_list('region', 'n')
        )
        return [
            {'key': key, 'label': str(label), 'count': counts[key]}
            for key, label in REGIONS
            if counts.get(key)
        ]
    except Exception:  # noqa: BLE001 — table missing / not migrated yet
        return []
```

`search_page.py`, append:

```python


def bar_context(request, variant: str, search: dict | None = None) -> dict:
    """Everything booking_marketplace/_search.html shows.

    The values come from the page's `search` on a results page and from the request on
    the home page. A phone shows `summary` and opens the form from it.
    """
    from plugins.installed.booking_marketplace.services import active_categories, live_regions

    variant = variant if variant in ('hero', 'bar', 'shop') else 'bar'
    if search is None:
        search = values(read_params(request) if request is not None else SearchParams())
    shop = variant == 'shop'
    summary = [search['q'] or (_('Search local goods') if shop else _('Any experience'))]
    if not shop:
        summary += [
            search['region_label'] or _('All of Montenegro'),
            search['date_label'] or _('Any date'),
        ]
    return {
        **search,
        'variant': variant,
        'action': '/shop/' if shop else '/bookings/',
        'regions': [] if shop else live_regions(),
        'categories': [] if shop else active_categories(),
        'summary': ' · '.join(summary),
        'suggest_url': (
            '' if shop or request is None else localized_path(request, '/bookings/suggest/')
        ),
        'date_locale': date_locale()[1],
        'today_iso': timezone.localdate().isoformat(),
    }
```

`templatetags/booking_tags.py`, after `booking_categories`:

```python
@register.simple_tag(takes_context=True)
def search_bar(context, variant='bar'):
    """Everything booking_marketplace/_search.html shows (search_page.bar_context)."""
    from plugins.installed.booking_marketplace.search_page import bar_context

    return bar_context(context.get('request'), variant, context.get('search'))
```

- [ ] **Step 4: The partial**

Create `themes/library/montenegro/templates/booking_marketplace/_search.html`:

```django
{% load i18n static booking_tags %}
{% comment %}The travel store's one search bar (docs/superpowers/specs/2026-10-14-montenegro-search-design.md).
`variant`: "hero" (the home page), "bar" (/bookings/) or "shop" (/shop/). It shows the page's
`search` — the view's validated values — or, on the home page, what the request asked
(booking_tags.search_bar). The form works without JavaScript; montenegro/search.js adds the
suggestions, the date's label, the clear buttons and, on a phone, the full-screen panel that the
summary line opens. Every field has a label tied to it.{% endcomment %}
{% search_bar variant as sb %}
<div class="mx-sb mx-sb--{{ sb.variant }}" data-mx-search="{{ sb.variant }}"{% if sb.suggest_url %} data-suggest-url="{{ sb.suggest_url }}"{% endif %} data-date-locale="{{ sb.date_locale }}" data-label-experiences="{% trans 'Experiences' %}" data-label-places="{% trans 'Places' %}" data-label-categories="{% trans 'Categories' %}">
  {% if sb.variant != 'hero' %}
  <button type="button" class="mx-sb__summary" data-sb-open aria-expanded="false" aria-controls="sb-form-{{ sb.variant }}">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
    <span class="mx-sr-only">{% trans "Edit search" %}: </span><span class="mx-sb__summary-text">{{ sb.summary }}</span>
  </button>
  {% endif %}
  <form id="sb-form-{{ sb.variant }}" class="mx-sb__form" action="{{ sb.action }}" method="get" role="search" data-sb-form>
    {% if sb.variant != 'hero' %}
    <div class="mx-sb__panel-head">
      <p class="mx-sb__panel-title" id="sb-title-{{ sb.variant }}">{% trans "Search" %}</p>
      <button type="button" class="mx-sb__icon-btn" data-sb-close aria-label="{% trans 'Close' %}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
    </div>
    {% endif %}
    <div class="mx-sb__field mx-sb__field--what">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      <div class="mx-sb__control">
        <label class="mx-sb__label" for="sb-q-{{ sb.variant }}">{% trans "What" %}</label>
        <input class="mx-sb__input" type="search" id="sb-q-{{ sb.variant }}" name="q" value="{{ sb.q }}" maxlength="200" autocomplete="off" enterkeyhint="search" data-sb-q placeholder="{% if sb.variant == 'shop' %}{% trans 'Search local goods' %}{% else %}{% trans 'Try kayaking, Kotor, wine…' %}{% endif %}"{% if sb.suggest_url %} role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="sb-list-{{ sb.variant }}"{% endif %}>
      </div>
      <button type="button" class="mx-sb__clear" data-sb-clear-q aria-label="{% trans 'Clear search' %}" hidden><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
      {% if sb.suggest_url %}<div class="mx-sb__popup" id="sb-list-{{ sb.variant }}" role="listbox" aria-label="{% trans 'Suggestions' %}" data-sb-list hidden></div>{% endif %}
    </div>
    {% if sb.variant != 'shop' %}
    <div class="mx-sb__field">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>
      <div class="mx-sb__control">
        <label class="mx-sb__label" for="sb-where-{{ sb.variant }}">{% trans "Where" %}</label>
        <select class="mx-sb__input" id="sb-where-{{ sb.variant }}" name="region">
          <option value="">{% trans "All of Montenegro" %}</option>
          {% for r in sb.regions %}<option value="{{ r.key }}"{% if r.key == sb.region %} selected{% endif %}>{{ r.label }} ({{ r.count }})</option>{% endfor %}
        </select>
      </div>
    </div>
    <div class="mx-sb__field mx-sb__field--when">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18M8 2v4M16 2v4"/></svg>
      <div class="mx-sb__control">
        <label class="mx-sb__label" for="sb-date-{{ sb.variant }}">{% trans "When" %}</label>
        <div class="mx-sb__date">
          <span class="mx-sb__date-text{% if sb.date_iso %} is-set{% endif %}" data-sb-date-text data-any="{% trans 'Any date' %}" aria-hidden="true">{% if sb.date_label %}{{ sb.date_label }}{% else %}{% trans "Any date" %}{% endif %}</span>
          <input class="mx-sb__input mx-sb__date-input" type="date" id="sb-date-{{ sb.variant }}" name="date" value="{{ sb.date_iso }}" min="{{ sb.today_iso }}" data-sb-date>
        </div>
      </div>
      <button type="button" class="mx-sb__clear" data-sb-clear-date aria-label="{% trans 'Clear date' %}" hidden><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
    </div>
    <div class="mx-sb__field mx-sb__field--category">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" x2="4" y1="21" y2="14"/><line x1="4" x2="4" y1="10" y2="3"/><line x1="12" x2="12" y1="21" y2="12"/><line x1="12" x2="12" y1="8" y2="3"/><line x1="20" x2="20" y1="21" y2="16"/><line x1="20" x2="20" y1="12" y2="3"/><line x1="2" x2="6" y1="14" y2="14"/><line x1="10" x2="14" y1="8" y2="8"/><line x1="18" x2="22" y1="16" y2="16"/></svg>
      <div class="mx-sb__control">
        <label class="mx-sb__label" for="sb-category-{{ sb.variant }}">{% trans "Category" %}</label>
        <select class="mx-sb__input" id="sb-category-{{ sb.variant }}" name="category">
          <option value="">{% trans "All categories" %}</option>
          {% for c in sb.categories %}<option value="{{ c.slug }}"{% if c.slug == sb.category %} selected{% endif %}>{{ c.name }}</option>{% endfor %}
        </select>
      </div>
    </div>
    {% endif %}
    <button type="submit" class="mx-sb__submit"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg><span>{% trans "Search" %}</span></button>
  </form>
</div>
<script src="{% static 'montenegro/search.js' %}" defer></script>
```

In `list.html`, replace the line

```django
  {% if not is_product_shop %}{% include "booking_marketplace/_search_bar.html" %}{% endif %}
```

with

```django
  {% if is_product_shop %}{% include "booking_marketplace/_search.html" with variant="shop" %}{% else %}{% include "booking_marketplace/_search.html" with variant="bar" %}{% endif %}
```

Then delete the old partial: `git rm themes/library/montenegro/templates/booking_marketplace/_search_bar.html`.

- [ ] **Step 5: The script**

Create `themes/library/montenegro/static/montenegro/search.js`:

```javascript
/* The travel store's search bar (booking_marketplace/_search.html).
 *
 * Suggestions while a visitor types (GET data-suggest-url?q=, 150 ms after the last key),
 * the date's label, the clear buttons and, on a phone, the full-screen panel the summary
 * line opens. The form works without this file. Text from the server is set with
 * textContent and a link must be a path on this site: nothing here is parsed as HTML.
 */
(function () {
  'use strict';

  var DEBOUNCE_MS = 150;
  var MIN_CHARS = 2;
  var MAX_CHARS = 80;
  var PHONE = window.matchMedia('(max-width: 767px)');

  function sitePath(url) {
    return typeof url === 'string' && url.charAt(0) === '/' && url.charAt(1) !== '/' ? url : '';
  }

  function make(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function initWhat(root) {
    var input = root.querySelector('[data-sb-q]');
    var clear = root.querySelector('[data-sb-clear-q]');
    if (!input || !clear) return;
    function sync() { clear.hidden = !input.value; }
    input.addEventListener('input', sync);
    clear.addEventListener('click', function () {
      input.value = '';
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.focus();
    });
    sync();
  }

  function initWhen(root) {
    var input = root.querySelector('[data-sb-date]');
    var text = root.querySelector('[data-sb-date-text]');
    var clear = root.querySelector('[data-sb-clear-date]');
    if (!input || !text) return;
    var anyDate = text.getAttribute('data-any') || '';
    var format = null;
    try {
      format = new Intl.DateTimeFormat(root.getAttribute('data-date-locale') || undefined, {
        weekday: 'short', day: 'numeric', month: 'short'
      });
    } catch (error) {
      format = null;
    }
    function label() {
      var parts = input.value.split('-');
      if (parts.length !== 3) return anyDate;
      var day = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
      return format && !isNaN(day.getTime()) ? format.format(day) : input.value;
    }
    function sync() {
      text.textContent = label();
      text.classList.toggle('is-set', Boolean(input.value));
      if (clear) clear.hidden = !input.value;
    }
    input.addEventListener('change', sync);
    input.addEventListener('click', function () {
      if (typeof input.showPicker === 'function') {
        try { input.showPicker(); } catch (error) { /* the native control still opens */ }
      }
    });
    if (clear) {
      clear.addEventListener('click', function () {
        input.value = '';
        sync();
        input.focus();
      });
    }
    sync();
  }

  function initSuggest(root) {
    var input = root.querySelector('[data-sb-q]');
    var list = root.querySelector('[data-sb-list]');
    var url = sitePath(root.getAttribute('data-suggest-url'));
    if (!input || !list || !url) return;
    var groups = [
      ['experiences', root.getAttribute('data-label-experiences') || ''],
      ['places', root.getAttribute('data-label-places') || ''],
      ['categories', root.getAttribute('data-label-categories') || '']
    ];
    var answers = new Map();
    var timer = 0;
    var pending = null;
    var options = [];
    var active = -1;

    function close() {
      list.hidden = true;
      list.textContent = '';
      options = [];
      active = -1;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
    }

    function select(index) {
      if (options[active]) options[active].setAttribute('aria-selected', 'false');
      active = index;
      var option = options[active];
      if (!option) {
        input.removeAttribute('aria-activedescendant');
        return;
      }
      option.setAttribute('aria-selected', 'true');
      input.setAttribute('aria-activedescendant', option.id);
      option.scrollIntoView({ block: 'nearest' });
    }

    function optionFor(item, group) {
      var href = sitePath(item && item.url);
      if (!href || !item.name) return null;
      var node = make('div', 'mx-sb__opt');
      node.id = list.id + '-' + options.length;
      node.setAttribute('role', 'option');
      node.setAttribute('aria-selected', 'false');
      node.setAttribute('data-href', href);
      if (group === 'experiences') {
        var thumb = make('span', 'mx-sb__thumb');
        var image = String(item.image || '');
        var src = sitePath(image) || (/^https:\/\//.test(image) ? image : '');
        if (src) {
          var img = make('img');
          img.src = src;
          img.alt = '';
          img.loading = 'lazy';
          thumb.appendChild(img);
        }
        node.appendChild(thumb);
      }
      var body = make('span', 'mx-sb__opt-body');
      body.appendChild(make('span', 'mx-sb__opt-name', String(item.name)));
      var meta = '';
      if (group === 'experiences') meta = [item.location, item.price].filter(Boolean).join(' · ');
      if (group === 'categories' && item.count) meta = String(item.count);
      if (meta) body.appendChild(make('span', 'mx-sb__opt-meta', meta));
      node.appendChild(body);
      options.push(node);
      return node;
    }

    function render(data) {
      list.textContent = '';
      options = [];
      active = -1;
      input.removeAttribute('aria-activedescendant');
      groups.forEach(function (group) {
        var items = (data && data[group[0]]) || [];
        if (!items.length) return;
        var box = make('div', 'mx-sb__group');
        box.setAttribute('role', 'group');
        var title = make('div', 'mx-sb__group-label', group[1]);
        title.id = list.id + '-' + group[0];
        box.setAttribute('aria-labelledby', title.id);
        box.appendChild(title);
        items.forEach(function (item) {
          var node = optionFor(item, group[0]);
          if (node) box.appendChild(node);
        });
        list.appendChild(box);
      });
      if (!options.length) {
        close();
        return;
      }
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    }

    function ask(q) {
      if (answers.has(q)) {
        render(answers.get(q));
        return;
      }
      if (pending) pending.abort();
      pending = typeof AbortController === 'function' ? new AbortController() : null;
      fetch(url + '?q=' + encodeURIComponent(q), {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
        signal: pending ? pending.signal : undefined
      })
        .then(function (response) { return response.ok ? response.json() : null; })
        .then(function (data) {
          if (!data) return;
          answers.set(q, data);
          if (input.value.trim() === q && document.activeElement === input) render(data);
        })
        .catch(function () { /* aborted or offline: the form still submits */ });
    }

    input.addEventListener('input', function () {
      window.clearTimeout(timer);
      var q = input.value.trim();
      if (q.length < MIN_CHARS || q.length > MAX_CHARS) {
        close();
        return;
      }
      timer = window.setTimeout(function () { ask(q); }, DEBOUNCE_MS);
    });
    input.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        if (list.hidden || !options.length) return;
        event.preventDefault();
        var step = event.key === 'ArrowDown' ? 1 : -1;
        if (active < 0) select(step > 0 ? 0 : options.length - 1);
        else select((active + step + options.length) % options.length);
      } else if (event.key === 'Enter' && !list.hidden && options[active]) {
        event.preventDefault();
        window.location.assign(options[active].getAttribute('data-href'));
      } else if (event.key === 'Escape' && !list.hidden) {
        event.preventDefault();
        close();
      }
    });
    input.addEventListener('blur', close);
    list.addEventListener('mousedown', function (event) { event.preventDefault(); });
    list.addEventListener('click', function (event) {
      var node = event.target.closest('[role="option"]');
      if (node) window.location.assign(node.getAttribute('data-href'));
    });
  }

  function initPanel(root) {
    var open = root.querySelector('[data-sb-open]');
    var form = root.querySelector('[data-sb-form]');
    var shut = root.querySelector('[data-sb-close]');
    if (!open || !form) return;
    var title = form.querySelector('.mx-sb__panel-title');

    function show() {
      root.classList.add('is-open');
      open.setAttribute('aria-expanded', 'true');
      form.setAttribute('role', 'dialog');
      form.setAttribute('aria-modal', 'true');
      if (title) form.setAttribute('aria-labelledby', title.id);
      document.documentElement.classList.add('mx-sb-locked');
      var first = form.querySelector('[data-sb-q]');
      if (first) first.focus();
    }

    function hide(restoreFocus) {
      if (!root.classList.contains('is-open')) return;
      root.classList.remove('is-open');
      open.setAttribute('aria-expanded', 'false');
      form.setAttribute('role', 'search');
      form.removeAttribute('aria-modal');
      form.removeAttribute('aria-labelledby');
      document.documentElement.classList.remove('mx-sb-locked');
      if (restoreFocus) open.focus();
    }

    function focusable() {
      return Array.prototype.filter.call(form.querySelectorAll('button, input, select'), function (node) {
        return !node.disabled && !node.hidden && node.type !== 'hidden' && node.offsetParent !== null;
      });
    }

    open.addEventListener('click', show);
    if (shut) shut.addEventListener('click', function () { hide(true); });
    form.addEventListener('keydown', function (event) {
      if (!root.classList.contains('is-open')) return;
      if (event.key === 'Escape' && !event.defaultPrevented) {
        hide(true);
        return;
      }
      if (event.key !== 'Tab') return;
      var nodes = focusable();
      if (!nodes.length) return;
      var first = nodes[0];
      var last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
    // Turned to a wider screen with the panel open: the page must scroll again.
    var widened = function (query) { if (!query.matches) hide(false); };
    if (PHONE.addEventListener) PHONE.addEventListener('change', widened);
  }

  function init(root) {
    if (root.hasAttribute('data-enhanced')) return;
    root.setAttribute('data-enhanced', '');
    initWhat(root);
    initWhen(root);
    initSuggest(root);
    initPanel(root);
  }

  Array.prototype.forEach.call(document.querySelectorAll('[data-mx-search]'), init);
})();
```

- [ ] **Step 6: The styles**

In `refresh.css`, insert this section just before the `@media (prefers-reduced-motion: reduce)` block at the end of the file:

```css
/* ── Search bar (booking_marketplace/_search.html, montenegro/search.js) ─────
   One bar on the home hero, /bookings/ and /shop/. On a phone the hero keeps its
   card and the listings show a summary line that opens the form full screen.
   Without JavaScript every field shows and the form submits as it is. */
.mx-sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}
.mx-sb { position: relative; z-index: 30; text-align: left; }
.mx-sb--hero { max-width: 56rem; margin: 0 auto; }
.mx-sb--shop { max-width: 40rem; }
.mx-sb__form {
  display: flex; flex-direction: column; gap: .25rem;
  padding: .5rem; border-radius: 1rem;
  background: hsl(var(--background));
  box-shadow: var(--shadow-elevated);
}
.mx-sb--bar .mx-sb__form,
.mx-sb--shop .mx-sb__form { border: 1px solid hsl(var(--border)); box-shadow: var(--shadow-soft); }
.mx-sb__panel-head { display: none; }
.mx-sb__field {
  position: relative; display: flex; align-items: center; gap: .75rem;
  min-width: 0; padding: .5rem .875rem; border-radius: .75rem;
  transition: background-color .15s ease;
}
.mx-sb__field:hover,
.mx-sb__field:focus-within { background: hsl(var(--muted) / .55); }
.mx-sb__field:has(.mx-sb__input:focus-visible) { box-shadow: inset 0 0 0 2px hsl(var(--ring)); }
.mx-sb__field > svg,
.mx-sb__summary > svg,
.mx-sb__submit > svg { flex: none; width: 1.25rem; height: 1.25rem; }
.mx-sb__field > svg { color: hsl(var(--muted-foreground)); }
.mx-sb__control { flex: 1; min-width: 0; }
.mx-sb__label {
  display: block; font-size: .75rem; font-weight: 600; line-height: 1rem;
  color: hsl(var(--foreground)); cursor: pointer;
}
.mx-sb__input {
  display: block; width: 100%; height: 1.5rem; margin: 0; padding: 0; border: 0;
  background: transparent; font: inherit; font-size: .9rem; color: hsl(var(--foreground));
  outline: none; -webkit-appearance: none; appearance: none;
}
select.mx-sb__input { cursor: pointer; text-overflow: ellipsis; }
.mx-sb__input::placeholder { color: hsl(var(--muted-foreground)); opacity: 1; }
.mx-sb__input::-webkit-search-cancel-button,
.mx-sb__input::-webkit-search-decoration { -webkit-appearance: none; display: none; }
.mx-sb__clear,
.mx-sb__icon-btn {
  position: relative; z-index: 1; flex: none;
  display: inline-flex; align-items: center; justify-content: center;
  width: 2rem; height: 2rem; padding: 0; border: 0; border-radius: 999px;
  background: transparent; color: hsl(var(--muted-foreground)); cursor: pointer;
}
.mx-sb__clear:hover,
.mx-sb__icon-btn:hover { background: hsl(var(--muted)); color: hsl(var(--foreground)); }
.mx-sb__clear svg,
.mx-sb__icon-btn svg { width: 1rem; height: 1rem; }
.mx-sb__clear[hidden] { display: none; }
.mx-sb__submit {
  display: inline-flex; align-items: center; justify-content: center; gap: .5rem;
  height: 3rem; padding: 0 1.5rem; border: 0; border-radius: .75rem;
  background: hsl(var(--primary)); color: hsl(var(--primary-foreground));
  font-size: .9rem; font-weight: 600; cursor: pointer;
  transition: background-color .15s ease;
}
.mx-sb__submit:hover { background: hsl(var(--primary) / .9); }
.mx-sb button:focus-visible { outline: 2px solid hsl(var(--ring)); outline-offset: 2px; }

/* When: the native date input lies over its label, so a tap opens the system picker. */
.mx-sb__date { position: relative; }
.mx-sb__date-text {
  display: none; height: 1.5rem; line-height: 1.5rem; font-size: .9rem;
  color: hsl(var(--muted-foreground));
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}
.mx-sb__date-text.is-set { color: hsl(var(--foreground)); }
[data-enhanced] .mx-sb__date-text { display: block; }
[data-enhanced] .mx-sb__date-input {
  position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer;
}

/* Suggestions */
.mx-sb__popup {
  position: absolute; top: calc(100% + .375rem); left: 0; z-index: 40;
  width: max(100%, 24rem); max-height: min(28rem, 70vh); overflow-y: auto;
  padding: .375rem; border: 1px solid hsl(var(--border)); border-radius: .875rem;
  background: hsl(var(--popover)); box-shadow: var(--shadow-elevated);
}
.mx-sb__popup[hidden] { display: none; }
.mx-sb__group + .mx-sb__group {
  margin-top: .25rem; padding-top: .25rem; border-top: 1px solid hsl(var(--border));
}
.mx-sb__group-label {
  padding: .375rem .625rem .25rem; font-size: .7rem; font-weight: 600;
  letter-spacing: .04em; text-transform: uppercase; color: hsl(var(--muted-foreground));
}
.mx-sb__opt {
  display: flex; align-items: center; gap: .75rem;
  padding: .5rem .625rem; border-radius: .625rem; cursor: pointer;
}
.mx-sb__opt:hover,
.mx-sb__opt[aria-selected="true"] { background: hsl(var(--muted)); }
.mx-sb__thumb {
  flex: none; width: 2.5rem; height: 2.5rem; overflow: hidden;
  border-radius: .5rem; background: hsl(var(--muted));
}
.mx-sb__thumb img { display: block; width: 100%; height: 100%; object-fit: cover; }
.mx-sb__opt-body { display: flex; flex-direction: column; min-width: 0; }
.mx-sb__opt-name,
.mx-sb__opt-meta { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.mx-sb__opt-name { font-size: .9rem; font-weight: 500; color: hsl(var(--foreground)); }
.mx-sb__opt-meta { font-size: .8rem; color: hsl(var(--muted-foreground)); }

.mx-sb__summary { display: none; }
@media (min-width: 768px) {
  .mx-sb__form { flex-direction: row; align-items: center; }
  .mx-sb__field { flex: 1 1 9rem; }
  .mx-sb__field--what { flex: 1.6 1 13rem; }
  .mx-sb__field + .mx-sb__field::before {
    content: ""; position: absolute; left: 0; top: 25%; width: 1px; height: 50%;
    background: hsl(var(--border));
  }
  .mx-sb__submit { flex: none; }
}
@media (max-width: 767px) {
  .mx-sb__field--category { display: none; }
  .mx-sb__popup { width: 100%; }
  .mx-sb__submit { width: 100%; }
  .mx-sb--hero .mx-sb__form { padding: .375rem; gap: 0; }
  .mx-sb--hero .mx-sb__field { padding: .4rem .75rem; }
  /* The listings: a summary line opens the form as a full-screen panel. */
  [data-enhanced].mx-sb--bar .mx-sb__summary,
  [data-enhanced].mx-sb--shop .mx-sb__summary {
    display: flex; align-items: center; gap: .75rem; width: 100%; height: 3.25rem;
    padding: 0 1rem; border: 1px solid hsl(var(--border)); border-radius: 999px;
    background: hsl(var(--background)); box-shadow: var(--shadow-soft);
    color: hsl(var(--foreground)); font: inherit; font-size: .9rem; font-weight: 500;
    text-align: left; cursor: pointer;
  }
  .mx-sb__summary > svg { color: hsl(var(--primary)); }
  .mx-sb__summary-text { min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
  [data-enhanced].mx-sb--bar .mx-sb__form,
  [data-enhanced].mx-sb--shop .mx-sb__form { display: none; }
  [data-enhanced].mx-sb.is-open { z-index: 90; }
  [data-enhanced].mx-sb.is-open .mx-sb__form {
    display: flex; position: fixed; inset: 0; z-index: 90; gap: .5rem;
    padding: 1rem 1rem calc(1rem + env(safe-area-inset-bottom));
    border: 0; border-radius: 0; box-shadow: none; overflow-y: auto;
  }
  [data-enhanced].mx-sb.is-open .mx-sb__panel-head {
    display: flex; align-items: center; justify-content: space-between; margin-bottom: .25rem;
  }
  .mx-sb__panel-title { font-size: 1.125rem; font-weight: 600; color: hsl(var(--foreground)); }
  [data-enhanced].mx-sb.is-open .mx-sb__field { border: 1px solid hsl(var(--border)); }
  [data-enhanced].mx-sb.is-open .mx-sb__submit { margin-top: auto; }
}
html.mx-sb-locked,
html.mx-sb-locked body { overflow: hidden; }
```

In the closing `@media (prefers-reduced-motion: reduce)` block, add the line `.mx-sb__field, .mx-sb__submit { transition: none; }`.

- [ ] **Step 7: Serbian for the new strings**

Append to `locale/sr/LC_MESSAGES/django.po`, checking each msgid with `grep -nF` first:

```po

msgid "Try kayaking, Kotor, wine…"
msgstr "Npr. kajak, Kotor, vino…"

msgid "Search local goods"
msgstr "Pretražite domaće proizvode"

msgid "Any experience"
msgstr "Bilo koji doživljaj"

msgid "All of Montenegro"
msgstr "Cijela Crna Gora"

msgid "Clear search"
msgstr "Obriši pretragu"

msgid "Clear date"
msgstr "Obriši datum"

msgid "Edit search"
msgstr "Uredi pretragu"

msgid "Close"
msgstr "Zatvori"

msgid "Suggestions"
msgstr "Prijedlozi"
```

Compile: `msgfmt --check-format -o locale/sr/LC_MESSAGES/django.mo locale/sr/LC_MESSAGES/django.po`

- [ ] **Step 8: Run the tests to see them pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_bar plugins.installed.booking_marketplace.tests.test_serbian_catalog plugins.installed.booking_marketplace.tests.test_search_results core.tests.test_css_comments`
Expected: `OK`.

- [ ] **Step 9: Lint and commit**

```bash
files=(plugins/installed/booking_marketplace/services.py plugins/installed/booking_marketplace/search_page.py plugins/installed/booking_marketplace/templatetags/booking_tags.py plugins/installed/booking_marketplace/tests/test_search_bar.py)
.venv/bin/ruff check --fix "${files[@]}" && .venv/bin/ruff format "${files[@]}"
git add "${files[@]}" themes/library/montenegro/templates/booking_marketplace/_search.html themes/library/montenegro/templates/booking_marketplace/list.html themes/library/montenegro/static/montenegro/search.js themes/library/montenegro/static/montenegro/refresh.css locale/sr/LC_MESSAGES/django.po locale/sr/LC_MESSAGES/django.mo
git commit -m "feat(montenegro): one search bar with suggestions, a readable date and a phone panel" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The results page says what was searched

**Files:**
- Modify (replace whole file): `themes/library/montenegro/templates/booking_marketplace/list.html`
- Modify: `themes/library/montenegro/static/montenegro/refresh.css` (the results section)
- Modify: `locale/sr/LC_MESSAGES/django.po` and `.mo`
- Test: `plugins/installed/booking_marketplace/tests/test_search_results_page.py`

**Interfaces:**
- Consumes:
  - the view context from Task 4: `search` (`heading`, `chips`, `clear_url`, `date_note`, `close`, `card_heading`, `empty_message`, `date_iso`), plus `q`, `region`, `category` and `sort`
  - the partial from Task 6
  - `{% booking_categories %}`, whose rows have `slug`
- Produces these markers (used by later tests and the live check):
  - `id="results-heading"`, `id="results-intro"`, `id="active-filters"`
  - `data-chip="<param>"`, `data-chip-clear`
  - `id="date-note"`, `id="results-count"`, `id="sort-form"`
  - `id="no-results"`, `id="close-matches"`
  - `data-popular-category="<slug>"`

- [ ] **Step 1: Write the failing tests**

Create `plugins/installed/booking_marketplace/tests/test_search_results_page.py`:

```python
"""The results page says what was searched (booking_marketplace/list.html).

The heading never reflected the search, the filters in force were invisible, the sort
form dropped the date, and zero results offered only "Clear filters".
"""

from __future__ import annotations

import datetime
import re

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace import search_page
from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.tests._i18n import serbian_enabled
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Category, Vendor


class PageFixture(MontenegroThemeMixin):
    def setUp(self):
        super().setUp()
        self.vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        water = Category.objects.create(name='Water Sports', slug='water-sports')
        BookableService.objects.create(
            vendor=self.vendor, name='Sunset Kayak Tour', slug='kotor-kayak', location='Kotor',
            region='kotor', category=water, price=Money(50, 'EUR'),
        )
        BookableService.objects.create(
            vendor=self.vendor, name='Kayak and Snorkel Tour', slug='budva-kayak', location='Budva',
            region='budva', category=water, price=Money(50, 'EUR'),
        )
        BookableService.objects.create(
            vendor=self.vendor, name='Wild Mountain Honey', slug='wild-honey', listing_kind='product',
            price=Money(9, 'EUR'),
        )
        self.day = timezone.localdate() + datetime.timedelta(days=6)

    def _body(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode()

    def _heading(self, body):
        return re.search(r'<h1 id="results-heading"[^>]*>(.*?)</h1>', body, re.S).group(1).strip()


@override_settings(BOOKING_LISTING_MODE=False)
class ResultsPageTests(PageFixture, TestCase):
    def test_the_heading_says_what_was_searched(self):
        self.assertEqual(
            self._heading(self._body('/bookings/?q=kayak&region=kotor')), '“kayak” in Kotor Bay'
        )
        self.assertEqual(
            self._heading(self._body('/bookings/?category=water-sports')),
            'Water Sports experiences in Montenegro',
        )
        self.assertEqual(self._heading(self._body('/bookings/')), 'Experiences in Montenegro')
        self.assertEqual(
            self._heading(self._body(f'/bookings/?q=kayak&date={self.day.isoformat()}')),
            f'“kayak” in Montenegro on {search_page.date_label(self.day)}',
        )

    def test_the_intro_steps_aside_for_a_search(self):
        self.assertIn('id="results-intro"', self._body('/bookings/'))
        self.assertNotIn('id="results-intro"', self._body('/bookings/?q=kayak'))

    def test_a_chip_per_filter_each_removing_itself(self):
        body = self._body(
            f'/bookings/?q=kayak&region=kotor&category=water-sports&date={self.day.isoformat()}'
        )
        chips = {
            param: href
            for href, param in re.findall(r'<a href="([^"]*)" class="mx-chip" data-chip="(\w+)"', body)
        }
        self.assertEqual(set(chips), {'q', 'region', 'date', 'category'})
        for param, href in chips.items():
            with self.subTest(param=param):
                self.assertNotIn(f'{param}=', href)
        self.assertRegex(body, r'<a href="/bookings/" class="mx-chips__clear" data-chip-clear>')

    def test_the_sort_form_keeps_every_filter(self):
        body = self._body(
            f'/bookings/?q=kayak&region=kotor&category=Water+Sports&date={self.day.isoformat()}'
        )
        form = re.search(r'<form id="sort-form".*?</form>', body, re.S).group(0)
        for name, value in (
            ('q', 'kayak'),
            ('region', 'kotor'),
            ('category', 'water-sports'),
            ('date', self.day.isoformat()),
        ):
            with self.subTest(name=name):
                self.assertIn(f'<input type="hidden" name="{name}" value="{value}">', form)
        self.assertRegex(form, r'<option value="best" selected>')
        plain = re.search(r'<form id="sort-form".*?</form>', self._body('/bookings/'), re.S).group(0)
        self.assertNotIn('value="best"', plain)

    def test_paging_keeps_the_date(self):
        for i in range(48):
            BookableService.objects.create(
                vendor=self.vendor, name=f'Extra {i}', slug=f'extra-{i}', price=Money(10, 'EUR')
            )
        body = self._body(f'/bookings/?date={self.day.isoformat()}')
        following = re.search(r'<a href="([^"]*)" rel="next"', body).group(1)
        self.assertIn(f'date={self.day.isoformat()}', following)
        self.assertIn('page=2', following)

    def test_nothing_found_names_the_search_and_offers_a_way_on(self):
        body = self._body(f'/bookings/?q=zzzz&date={self.day.isoformat()}')
        self.assertIn('id="no-results"', body)
        self.assertIn(f'No experiences match “zzzz” on {search_page.date_label(self.day)}', body)
        self.assertIn('data-popular-category="water-sports"', body)
        self.assertIn('href="/bookings/?category=water-sports"', body)
        self.assertNotIn('id="results-count"', body)

    def test_close_matches_are_labelled(self):
        body = self._body('/bookings/?q=kayak+ulcinj')
        self.assertIn('id="close-matches"', body)
        self.assertIn('No experiences match “kayak ulcinj”', body)
        self.assertRegex(body, r'<h3[^>]*><a href="/bookings/kotor-kayak/" class="card-link">')
        self.assertNotIn('id="results-count"', body)

    def test_a_past_date_says_so(self):
        yesterday = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        self.assertIn('id="date-note"', self._body(f'/bookings/?date={yesterday}'))

    def test_the_query_is_escaped(self):
        body = self._body('/bookings/?q=%3Cscript%3Ealert(1)%3C/script%3E')
        self.assertNotIn('<script>alert(1)</script>', body)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', body)

    def test_the_shop_says_what_it_found(self):
        body = self._body('/shop/?q=zzzz')
        self.assertIn('No products match “zzzz”', body)
        self.assertIn('data-chip="q"', body)
        self.assertIn('id="no-results"', body)
        self.assertEqual(self._heading(self._body('/shop/?q=honey')), 'Shop Montenegro')


class ChipLinkTests(SimpleTestCase):
    def test_a_chip_drops_its_parameter_and_the_page(self):
        request = RequestFactory().get(
            '/bookings/', {'q': 'kayak', 'region': 'kotor', 'page': '2', 'sort': 'rating'}
        )
        params = search_page.SearchParams(q='kayak', region='kotor', region_label='Kotor Bay')
        chips = {chip['param']: chip['href'] for chip in search_page.chips(request, params)}
        self.assertEqual(chips['q'], '/bookings/?region=kotor&sort=rating')
        self.assertEqual(chips['region'], '/bookings/?q=kayak&sort=rating')


@serbian_enabled
@override_settings(BOOKING_LISTING_MODE=False)
class SerbianResultsPageTests(PageFixture, TestCase):
    def test_serbian_heading(self):
        self.assertEqual(self._heading(self._body('/sr/bookings/?q=kajak')), '„kajak“ u Crnoj Gori')
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_results_page`
Expected: FAIL/ERROR. `results-heading`, `mx-chip`, `sort-form` and `no-results` do not exist yet, so the `re.search(...).group` calls raise `AttributeError: 'NoneType'`. `ChipLinkTests` passes, because its function landed in Task 4.

- [ ] **Step 3: Replace `list.html`**

Replace the whole of `themes/library/montenegro/templates/booking_marketplace/list.html` with:

```django
{% extends "storefront/base.html" %}
{% load morph %}{% load i18n %}{% load booking_tags %}{% load seo %}
{% comment %}1:1 with pages/Search.tsx — the search bar, the filters in force, count/sort row + grid.
Context: services, listing_mode, region, q, category (a slug), sort, and `search`
(booking_marketplace/search_page.page_context: heading, chips, date_note, close,
empty_message, card_heading).{% endcomment %}
{% comment %}Title, description, breadcrumbs and the ItemList come from the head
document (`seo_title`, `jsonld_items`, `breadcrumb_items` in the view's context).
This template used to paste its own ld+json beside it — plus a FAQPage whose
questions appeared nowhere on the page, on /shop/ as much as /bookings/.
`/shop/` renders here too (`is_product_shop`): it gets its own heading, count, search
bar and empty state, and none of the experience-only sort and buying guide.{% endcomment %}

{% block content %}
{% booking_listing_mode as listing_mode %}
<div class="container mx-auto px-4 py-8">
  <header class="mb-6">
    {% if is_product_shop %}
    <h1 id="results-heading" class="text-2xl md:text-3xl font-semibold text-foreground tracking-tight mb-2">{% trans "Shop Montenegro" %}</h1>
    {% if not search.chips %}<p id="results-intro" class="text-muted-foreground leading-7 max-w-3xl">{% trans "Locally made Montenegrin products from trusted vendors — shipped or ready for pickup across the Adriatic coast." %}</p>{% endif %}
    {% else %}
    <h1 id="results-heading" class="text-2xl md:text-3xl font-semibold text-foreground tracking-tight mb-2">{{ search.heading }}</h1>
    {% if not search.chips %}<p id="results-intro" class="text-muted-foreground leading-7 max-w-3xl">{% trans "Explore the Bay of Kotor by boat, hike in Durmitor, raft the Tara Canyon or meet local food and wine producers. Compare activities by destination, pace and travel style." %}</p>{% endif %}
    {% endif %}
  </header>

  {% if is_product_shop %}{% include "booking_marketplace/_search.html" with variant="shop" %}{% else %}{% include "booking_marketplace/_search.html" with variant="bar" %}{% endif %}

  {% if search.chips %}
  <div id="active-filters" class="mx-chips" role="group" aria-label="{% trans 'Active filters' %}">
    {% for chip in search.chips %}<a href="{{ chip.href }}" class="mx-chip" data-chip="{{ chip.param }}" aria-label="{% blocktrans with label=chip.label %}Remove filter {{ label }}{% endblocktrans %}"><span>{{ chip.label }}</span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg></a>{% endfor %}
    <a href="{{ search.clear_url }}" class="mx-chips__clear" data-chip-clear>{% trans "Clear all" %}</a>
  </div>
  {% endif %}
  {% if search.date_note %}<p id="date-note" class="mx-results__note" role="status">{{ search.date_note }}</p>{% endif %}

  {% if services and not search.close %}
  <!-- Count + sort row -->
  <div class="mx-results__bar">
    {% if is_product_shop %}
    <p id="results-count" class="mx-results__count">{% blocktrans count c=services|length %}{{ c }} product{% plural %}{{ c }} products{% endblocktrans %}</p>
    {% else %}
    <p id="results-count" class="mx-results__count">{% blocktrans count c=page_obj.paginator.count %}{{ c }} experience{% plural %}{{ c }} experiences{% endblocktrans %}</p>
    <form id="sort-form" method="get" class="flex items-center gap-2">
      {% if q %}<input type="hidden" name="q" value="{{ q }}">{% endif %}
      {% if region %}<input type="hidden" name="region" value="{{ region }}">{% endif %}
      {% if category %}<input type="hidden" name="category" value="{{ category }}">{% endif %}
      {% if search.date_iso %}<input type="hidden" name="date" value="{{ search.date_iso }}">{% endif %}
      <label for="sort-by" class="text-sm text-muted-foreground hidden sm:inline">{% trans "Sort by" %}</label>
      <select id="sort-by" name="sort" onchange="this.form.submit()" class="h-9 rounded-lg border border-border bg-card px-3 text-sm font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer">
        {% if q %}<option value="best" {% if sort == 'best' %}selected{% endif %}>{% trans "Best match" %}</option>{% endif %}
        <option value="recommended" {% if sort == 'recommended' %}selected{% endif %}>{% trans "Recommended" %}</option>
        <option value="rating" {% if sort == 'rating' %}selected{% endif %}>{% trans "Top rated" %}</option>
        {% if not listing_mode %}
        <option value="price_low" {% if sort == 'price_low' %}selected{% endif %}>{% trans "Price: low to high" %}</option>
        <option value="price_high" {% if sort == 'price_high' %}selected{% endif %}>{% trans "Price: high to low" %}</option>
        {% endif %}
        <option value="newest" {% if sort == 'newest' %}selected{% endif %}>{% trans "Newest" %}</option>
      </select>
    </form>
    {% endif %}
  </div>
  {% endif %}

  {% if services %}
  {% if search.close %}
  <div id="no-results" class="mx-empty mx-empty--close">
    <p class="mx-empty__title">{{ search.empty_message }}</p>
  </div>
  <h2 id="close-matches" class="mx-results__close">{% trans "Close matches" %}</h2>
  {% endif %}
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
    {% for s in services %}
    {% include "booking_marketplace/_experience_card.html" with s=s listing_mode=listing_mode heading=search.card_heading %}
    {% endfor %}
  </div>
  {% if page_obj.has_other_pages %}
  <nav aria-label="{% trans 'Pages' %}" class="flex flex-wrap items-center justify-center gap-2 mt-10 pt-6 border-t border-border">
    {% if page_obj.has_previous %}<a href="{% page_href page_obj.previous_page_number %}" rel="prev" class="inline-flex items-center h-10 px-4 rounded-lg border border-input bg-background text-sm font-medium text-foreground hover:bg-muted transition-colors">{% trans "Previous" %}</a>{% endif %}
    <span class="px-4 text-sm text-muted-foreground">{% blocktrans with n=page_obj.number total=page_obj.paginator.num_pages %}Page {{ n }} of {{ total }}{% endblocktrans %}</span>
    {% if page_obj.has_next %}<a href="{% page_href page_obj.next_page_number %}" rel="next" class="inline-flex items-center h-10 px-4 rounded-lg border border-input bg-background text-sm font-medium text-foreground hover:bg-muted transition-colors">{% trans "Next" %}</a>{% endif %}
  </nav>
  {% endif %}
  {% else %}
  <div id="no-results" class="mx-empty">
    <p class="mx-empty__title">{{ search.empty_message }}</p>
    {% if not is_product_shop %}
    {% booking_categories as popular %}
    {% if popular %}
    <p class="mx-empty__hint">{% trans "Popular categories" %}</p>
    <div class="mx-empty__cats">{% for c in popular|slice:":6" %}<a href="/bookings/?category={{ c.slug }}" class="mx-chip" data-popular-category="{{ c.slug }}"><span>{{ c.name }}</span></a>{% endfor %}</div>
    {% endif %}
    {% endif %}
    <p class="mx-empty__clear"><a href="{% if is_product_shop %}{% url 'booking_marketplace:shop' %}{% else %}{% url 'booking_marketplace:list' %}{% endif %}" class="text-primary underline">{% trans "Clear filters" %}</a></p>
  </div>
  {% endif %}

  {% if not is_product_shop %}
  <section class="mt-12 rounded-2xl border border-border bg-card p-5 md:p-7">
    <h2 class="text-2xl font-semibold text-foreground mb-3">{% trans "How to choose a Montenegro experience" %}</h2>
    <p class="text-muted-foreground leading-7 max-w-4xl">{% trans "Choose coastal boat trips and old-town walks for an easy first visit, mountain activities for active itineraries, and food or wine experiences for a slower local perspective. Check meeting points, duration and transport before confirming." %}</p>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-5 mt-6">
      <article><h3 class="font-semibold text-foreground mb-2">{% trans "Best for first-time visitors" %}</h3><p class="text-sm text-muted-foreground leading-6">{% trans "Start with Kotor, Perast and the bay, then add a day around Budva or Lake Skadar." %}</p></article>
      <article><h3 class="font-semibold text-foreground mb-2">{% trans "Best for active trips" %}</h3><p class="text-sm text-muted-foreground leading-6">{% trans "Look for Tara rafting, Durmitor hiking, kayaking and guided canyon or mountain routes." %}</p></article>
      <article><h3 class="font-semibold text-foreground mb-2">{% trans "Best for local culture" %}</h3><p class="text-sm text-muted-foreground leading-6">{% trans "Choose old-town walks, monastery visits, village food, wine tastings and host-led workshops." %}</p></article>
    </div>
    <div class="flex flex-wrap gap-3 mt-6 text-sm font-medium">
      <a href="/places/" class="text-primary hover:underline">{% trans "Explore destinations" %}</a>
      <a href="/journal/" class="text-primary hover:underline">{% trans "Read local travel guides" %}</a>
      <a href="/hotels/" class="text-primary hover:underline">{% trans "Find a place to stay" %}</a>
    </div>
  </section>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 4: The styles**

In `refresh.css`, insert this section after the search-bar section from Task 6, still before the reduced-motion block:

```css
/* ── Search results (booking_marketplace/list.html) ─────────────────────── */
#results-heading { overflow-wrap: anywhere; }
.mx-chips { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; margin-top: 1rem; }
.mx-chip {
  display: inline-flex; align-items: center; gap: .375rem; max-width: 100%;
  height: 2rem; padding: 0 .75rem; border: 1px solid hsl(var(--border)); border-radius: 999px;
  background: hsl(var(--card)); color: hsl(var(--foreground)); font-size: .85rem;
  text-decoration: none; transition: border-color .15s ease;
}
.mx-chip > span { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.mx-chip > svg {
  flex: none; width: .875rem; height: .875rem; margin-right: -.25rem;
  color: hsl(var(--muted-foreground));
}
.mx-chip:hover,
.mx-chip:focus-visible { border-color: hsl(var(--primary)); }
.mx-chips__clear {
  font-size: .85rem; font-weight: 500; color: hsl(var(--primary));
  text-decoration: underline; text-underline-offset: 2px;
}
.mx-results__note { margin-top: .75rem; font-size: .875rem; color: hsl(var(--destructive)); }
.mx-results__bar {
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
  gap: .75rem; margin: 1.5rem 0 1.25rem;
}
.mx-results__count { font-size: .875rem; color: hsl(var(--muted-foreground)); }
.mx-results__close { margin: 0 0 1rem; font-size: 1.25rem; font-weight: 600; color: hsl(var(--foreground)); }
.mx-empty { padding: 2.5rem 0 1rem; text-align: center; }
.mx-empty--close { padding: 1.5rem 0 .5rem; text-align: left; }
.mx-empty__title {
  font-size: 1.125rem; font-weight: 600; color: hsl(var(--foreground)); overflow-wrap: anywhere;
}
.mx-empty__hint { margin-top: 1rem; font-size: .875rem; color: hsl(var(--muted-foreground)); }
.mx-empty__cats { display: flex; flex-wrap: wrap; justify-content: center; gap: .5rem; margin-top: .75rem; }
.mx-empty__clear { margin-top: 1.5rem; }
```

and add `.mx-chip { transition: none; }` to the reduced-motion block.

- [ ] **Step 5: Serbian for the new strings**

Append to `locale/sr/LC_MESSAGES/django.po`, checking each msgid with `grep -nF` first. `"Clear all"` already exists, so do not add it.

```po

msgid "Best match"
msgstr "Najrelevantnije"

msgid "Active filters"
msgstr "Aktivni filteri"

#, python-format
msgid "Remove filter %(label)s"
msgstr "Ukloni filter %(label)s"

msgid "Close matches"
msgstr "Približni rezultati"

msgid "Popular categories"
msgstr "Popularne kategorije"
```

Compile: `msgfmt --check-format -o locale/sr/LC_MESSAGES/django.mo locale/sr/LC_MESSAGES/django.po`

- [ ] **Step 6: Run the tests to see them pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_results_page plugins.installed.booking_marketplace.tests.test_search_bar plugins.installed.booking_marketplace.tests.test_search_results plugins.installed.booking_marketplace.tests.test_serbian_catalog plugins.installed.booking_marketplace.tests.test_experience_card_titles plugins.installed.booking_marketplace.tests.test_booking core.tests.test_css_comments`
Expected: `OK`. That includes `I18nTests.test_serbian_list_heading`, whose heading now comes from the view.

- [ ] **Step 7: Lint and commit**

```bash
.venv/bin/ruff check --fix plugins/installed/booking_marketplace/tests/test_search_results_page.py && .venv/bin/ruff format plugins/installed/booking_marketplace/tests/test_search_results_page.py
git add plugins/installed/booking_marketplace/tests/test_search_results_page.py themes/library/montenegro/templates/booking_marketplace/list.html themes/library/montenegro/static/montenegro/refresh.css locale/sr/LC_MESSAGES/django.po locale/sr/LC_MESSAGES/django.mo
git commit -m "feat(montenegro): the results page names the search, its filters and its close matches" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: The home page — one bar, category links by slug

**Files:**
- Modify: `themes/library/montenegro/templates/storefront/home.html`:
  - the tag loads
  - the hero (search form, pills, overflow)
  - the inline date script
  - the Popular Experiences tabs
- Modify: `plugins/installed/booking_marketplace/templatetags/booking_tags.py`:
  - `_cat_href` takes a slug
  - `home_categories` passes it
  - remove `hero_pills`, `featured_filters` and `booking_regions`
- Modify: `plugins/installed/booking_marketplace/context_processors.py` (the menu links by slug)
- Modify: `themes/library/montenegro/static/montenegro/refresh.css`. Remove the rules nothing uses any more: `.mx-search-what`, `.mx-hide-phone` and `.mx-pill`.
- Modify: `plugins/installed/booking_marketplace/tests/test_nav_derived.py`
- Test: `plugins/installed/booking_marketplace/tests/test_search_home.py`

**Interfaces:**
- Consumes:
  - the partial (Task 6)
  - `booking_categories` rows with `slug` (Task 5)
- Produces: every category link on the store has the form `/bookings/?category=<slug>`.

- [ ] **Step 1: Write the failing tests**

Create `plugins/installed/booking_marketplace/tests/test_search_home.py`:

```python
"""The home page has one search bar and links categories by slug.

The hero carried its own copy of the search form and four category pills, so the page
showed the categories three times; and every category link used the name, which the
filter matched loosely while the menu's slug links found nothing.
"""

from __future__ import annotations

from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.booking_marketplace.context_processors import _nav_categories
from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Category, Vendor


@override_settings(BOOKING_LISTING_MODE=False)
class HomeSearchTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        super().setUp()
        vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        water = Category.objects.create(name='Water Sports', slug='water-sports')
        BookableService.objects.create(
            vendor=vendor, name='Sunset Kayak Tour', slug='kotor-kayak', region='kotor',
            category=water, price=Money(50, 'EUR'),
        )

    def _home(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _hero(self, body):
        start = body.rfind('<section', 0, body.index('data-mx-search="hero"'))
        return body[start : body.index('</section>', start)]

    def test_one_search_bar(self):
        body = self._home()
        self.assertEqual(body.count('data-mx-search='), 1)
        self.assertIn('data-mx-search="hero"', body)
        self.assertEqual(body.count('name="q"'), 1)

    def test_the_hero_has_no_category_pills(self):
        self.assertNotIn('/bookings/?category=', self._hero(self._home()))

    def test_the_hero_lets_the_suggestions_open_below_it(self):
        hero = self._hero(self._home())
        self.assertNotIn('overflow-hidden', hero[: hero.index('>')])

    def test_category_links_use_the_slug(self):
        body = self._home()
        self.assertIn('href="/bookings/?category=water-sports"', body)
        self.assertNotIn('category=Water', body)

    def test_the_menu_links_categories_by_slug(self):
        self.assertEqual([tile['href'] for tile in _nav_categories()], ['/bookings/?category=water-sports'])
```

In `plugins/installed/booking_marketplace/tests/test_nav_derived.py`:
- change the import block to `from plugins.installed.booking_marketplace.templatetags.booking_tags import (home_categories, home_testimonials)`
- delete `test_hero_pills_derive` and `test_featured_filters_derive`
- in `test_home_categories_have_links_and_icons`, change the expected href to `self.assertIn('/bookings/?category=adventure', cats[0]['href'])`

- [ ] **Step 2: Run the tests to see them fail**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_home plugins.installed.booking_marketplace.tests.test_nav_derived`
Expected:
- `test_one_search_bar` and the two `_hero` tests ERROR, because the home page has no `data-mx-search`.
- `test_category_links_use_the_slug`, `test_the_menu_links_categories_by_slug` and `test_home_categories_have_links_and_icons` FAIL, because the links still use `category=Water%20Sports` and `category=Adventure`.

- [ ] **Step 3: Links by slug, and the unused tags go**

In `booking_tags.py`:

```python
def _cat_href(slug):
    return f'/bookings/?category={quote(slug)}'
```

In `home_categories`, change `'href': _cat_href(c['name']),` to `'href': _cat_href(c['slug']),`. Then delete the three functions `hero_pills`, `featured_filters` and `booking_regions`: each one's `@register.simple_tag` decorator, its `def` and its body. After Step 4 nothing renders them. Confirm with `grep -rn "hero_pills\|featured_filters\|booking_regions" plugins themes`, which should print only the lines you are deleting, then nothing.

In `context_processors.py` `_nav_categories`, change `'href': _cat_href(c['name']),` to `'href': _cat_href(c['slug']),`.

- [ ] **Step 4: The home page**

Apply these edits to `home.html` with this script, run from the repo root. It asserts each anchor exists exactly once:

```bash
.venv/bin/python - <<'EOF'
from pathlib import Path

path = Path('themes/library/montenegro/templates/storefront/home.html')
text = path.read_text()


def swap(old, new):
    global text
    assert text.count(old) == 1, old[:70]
    text = text.replace(old, new)


swap('{% hero_pills as hero_pills %}\n', '')
swap('{% featured_filters as featured_filters %}\n', '{% booking_categories as tab_categories %}\n')
swap('{% booking_regions as hero_regions %}\n', '')
swap(
    '<section class="relative min-h-[360px] sm:min-h-[440px] lg:min-h-[560px] flex items-center overflow-hidden">\n'
    '  <div class="absolute inset-0">',
    '<section class="relative min-h-[360px] sm:min-h-[440px] lg:min-h-[560px] flex items-center">\n'
    '  <div class="absolute inset-0 overflow-hidden">',
)
start = text.index('      <!-- Hero search — 1:1 with SearchBar variant="hero"')
end = text.index('    </div>\n  </div>\n</section>', start)
text = (
    text[:start]
    + '      {% comment %}The one search bar (booking_marketplace/_search.html). The image layer clips\n'
    + '      its overflow, not the section, so the suggestions can open below the hero.{% endcomment %}\n'
    + '      {% include "booking_marketplace/_search.html" with variant="hero" %}\n'
    + text[end:]
)
start = text.index('{% comment %}A date input cannot show a placeholder')
end = text.index('</script>\n', start) + len('</script>\n')
text = text[:start] + text[end:]
swap(
    '      {% for f in featured_filters %}\n'
    '      <a href="/bookings/?category={{ f|urlencode }}"\n'
    '         class="px-4 py-2 rounded-full text-sm font-medium border border-border text-foreground hover:bg-muted transition-colors">{{ f }}</a>\n'
    '      {% endfor %}',
    '      {% for c in tab_categories %}\n'
    '      <a href="/bookings/?category={{ c.slug }}"\n'
    '         class="px-4 py-2 rounded-full text-sm font-medium border border-border text-foreground hover:bg-muted transition-colors">{{ c.name }}</a>\n'
    '      {% endfor %}',
)
path.write_text(text)
print('home.html updated')
EOF
```

Expected: `home.html updated`. Then `grep -n "hero_pills\|featured_filters\|hero_regions\|data-mx-any-date\|mx-pill" themes/library/montenegro/templates/storefront/home.html` prints nothing.

- [ ] **Step 5: Drop the CSS nothing uses any more**

In `refresh.css`:
- Delete the whole `/* ── Hero search ── */` section: its comment, the `.mx-search-what` media rule, the `.mx-hide-phone` media rule and the two `.mx-pill` rules.
- In the reduced-motion block, change `.mx-pill, .mx-catstrip__item { transition: none; }` to `.mx-catstrip__item { transition: none; }` and delete `.mx-pill:hover { transform: none; }`.
- Confirm with `grep -rn "mx-search-what\|mx-hide-phone\|mx-pill" themes plugins`, which should print nothing.

- [ ] **Step 6: Run the tests to see them pass**

Run: `$TEST plugins.installed.booking_marketplace.tests.test_search_home plugins.installed.booking_marketplace.tests.test_nav_derived plugins.installed.booking_marketplace.tests.test_booking plugins.installed.booking_marketplace.tests.test_montenegro_shell plugins.installed.booking_marketplace.tests.test_montenegro_storefront_claims plugins.installed.booking_marketplace.tests.test_serbian_catalog themes core.tests.test_css_comments`
Expected: `OK`. The `themes` label runs the head-contract and global-slot guards over the Montenegro theme.

- [ ] **Step 7: Lint and commit**

```bash
files=(plugins/installed/booking_marketplace/templatetags/booking_tags.py plugins/installed/booking_marketplace/context_processors.py plugins/installed/booking_marketplace/tests/test_nav_derived.py plugins/installed/booking_marketplace/tests/test_search_home.py)
.venv/bin/ruff check --fix "${files[@]}" && .venv/bin/ruff format "${files[@]}"
git add "${files[@]}" themes/library/montenegro/templates/storefront/home.html themes/library/montenegro/static/montenegro/refresh.css
git commit -m "feat(montenegro): the home page uses the one search bar and links categories by slug" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Check on the real content, release, deploy, verify live

**Files:**
- Modify:
  - `CLAUDE.md`: one convention paragraph, and one sentence in the i18n landmine
  - `docs/superpowers/specs/2026-10-14-montenegro-search-design.md`: a status line
- Through `manage.py release`: `morph/settings.py` and `docs/RELEASE_NOTES.md`, with the before/after table added by hand.
- Scratch files only, never committed: in `S=/private/tmp/claude-502/-Users-magnetoid-coding-morph/ea077053-0f76-43ff-a44e-08fa22583365/scratchpad/search` (in a new session, use that session's scratchpad).

**Interfaces:**
- Consumes everything above.
- Produces v0.112.0, live on all stores.

- [ ] **Step 1: The gates, on the whole tree**

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check .
DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py check
DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python scripts/check_core_boundary.py && .venv/bin/python scripts/check_plugin_boundary.py && .venv/bin/python scripts/check_plugin_standard.py
DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py test > $S/full-suite.log 2>&1; echo "exit=$?"; grep -E "^Ran |^OK|^FAILED" $S/full-suite.log | tail -3; grep -E "^(ERROR|FAIL):" $S/full-suite.log | head -20
```

Expected:
- every gate passes
- the boundary ratchets stay at 0, 113 and 38
- `makemigrations` reports "No changes detected" (no model changed)
- the suite prints `OK` with about 4,800 tests

Any failure is fixed before going on, with the cause ledgered.

- [ ] **Step 2: The live content, read only**

Save the dump script as `$S/dump_live.py`:

```python
import json
from plugins.installed.booking_marketplace.models import BookableService, Place

rows = [
    {
        'kind': s.listing_kind, 'slug': s.slug, 'name': s.name, 'location': s.location,
        'region': s.region, 'category': s.category.name if s.category_id else '',
        'category_slug': s.category.slug if s.category_id else '', 'highlights': s.highlights,
        'short': s.short_description, 'description': s.description, 'bestseller': s.is_bestseller,
        'price': str(s.price.amount), 'daily_capacity': s.daily_capacity,
    }
    for s in BookableService.objects.filter(is_active=True, vendor__is_active=True).select_related('category')
]
places = [{'name': p.name, 'slug': p.slug, 'region': p.region} for p in Place.objects.filter(is_active=True)]
print('JSONSTART' + json.dumps({'listings': rows, 'places': places}) + 'JSONEND')
```

Then run it and save its output:

```bash
WEB=$(~/.ssh/tetra-ssh.sh "docker ps --format '{{.Names}}' | grep '^web-fo8rvcg94bmcyi43e8iq9tvm'" | tail -1)
~/.ssh/tetra-ssh.sh "docker exec -i $WEB python manage.py shell" < $S/dump_live.py 2>/dev/null \
  | python3 -c "import re,sys; open('$S/live_docs.json','w').write(re.search(r'JSONSTART(.*)JSONEND', sys.stdin.read(), re.S).group(1))"
python3 -c "import json; d=json.load(open('$S/live_docs.json')); print(len(d['listings']), 'listings', len(d['places']), 'places')"
```

Expected: about `142 listings 26 places`.

- [ ] **Step 3: A local store with that content**

Save the loader as `$S/load_live.py`:

```python
import json, os
from djmoney.money import Money
from plugins.installed.booking_marketplace.models import BookableService, Place
from plugins.installed.catalog.models import Category, Vendor

data = json.load(open(os.environ['LIVE_DOCS']))
host, _ = Vendor.objects.get_or_create(slug='local-host', defaults={'name': 'Local host', 'is_active': True})
categories = {}
for row in data['listings']:
    if row['category_slug'] and row['category_slug'] not in categories:
        categories[row['category_slug']], _ = Category.objects.get_or_create(
            slug=row['category_slug'], defaults={'name': row['category']}
        )
for row in data['listings']:
    BookableService.objects.update_or_create(slug=row['slug'], defaults={
        'vendor': host, 'name': row['name'], 'location': row['location'], 'region': row['region'],
        'category': categories.get(row['category_slug']), 'highlights': row['highlights'],
        'short_description': row['short'][:300], 'description': row['description'],
        'listing_kind': row['kind'], 'is_bestseller': row['bestseller'],
        'price': Money(row['price'], 'EUR'), 'daily_capacity': row['daily_capacity'], 'is_active': True,
    })
for row in data['places']:
    Place.objects.update_or_create(slug=row['slug'], defaults={'name': row['name'], 'region': row['region'], 'is_active': True})
print(BookableService.objects.count(), 'listings', Place.objects.count(), 'places')
```

Then build the local store:

```bash
export DATABASE_URL="sqlite:///$S/smoke.sqlite3" REDIS_URL='redis://127.0.0.1:6379/14' \
  MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace' MORPHEUS_ACTIVE_THEME=montenegro \
  MORPHEUS_LANGUAGES='en,sr' DEBUG=True LIVE_DOCS="$S/live_docs.json"
.venv/bin/python manage.py migrate --noinput > $S/migrate.log 2>&1; tail -2 $S/migrate.log
.venv/bin/python manage.py shell < $S/load_live.py
```

Expected: `142 listings 26 places`. Migration `booking_marketplace 0002` switches the app on.

- [ ] **Step 4: The before/after table, through the real view**

Save the probe script as `$S/probe_after.py`:

```python
from django.test import Client
from django.test.utils import setup_test_environment

setup_test_environment()
client = Client()
PROBES = [
    ('q', 'kayak'), ('q', 'kayak kotor'), ('q', 'rafting tara'), ('q', 'sunset budva'),
    ('q', 'blue cave tivat'), ('q', 'wine tasting podgorica'), ('q', 'kajak'), ('q', 'kayac'),
    ('q', 'zabljak'), ('region', 'kotor'), ('category', 'wine'), ('category', 'water-sports'),
]
for param, value in PROBES:
    response = client.get('/bookings/', {param: value})
    found = response.context['page_obj'].paginator.count
    close = ' (close matches)' if response.context['search']['close'] else ''
    top = '; '.join(s.name for s in response.context['services'][:3])
    print(f'| `{param}={value}` | {found}{close} | {top} |')
```

Then run it: `.venv/bin/python manage.py shell < $S/probe_after.py > $S/after.md; cat $S/after.md`

Check against the spec's success criteria:
- `kayak kotor` puts the Kotor kayak tours first
- `zabljak` finds the Durmitor experiences
- `kajak` and `kayac` find kayaking
- `blue cave tivat` puts the Blue Cave boats from Tivat first

A miss is a finding. Write a failing test in `test_search_engine.py` with the shape that missed, fix the synonym or weight, rerun Steps 1 and 4, and record a `Ruling:` line.

"Before" comes from the spec, measured live on 2026-10-14:

| Probe | Before |
|---|---|
| `kayak` | 7 |
| `kayak kotor`, `rafting tara`, `sunset budva`, `blue cave tivat`, `wine tasting podgorica` | 0 |
| `kajak`, `kayac`, `zabljak` | 0 |
| `region=kotor` | 41 |
| `category=wine` | 9 |
| `category=water-sports` | 0 |

- [ ] **Step 5: In a browser, before shipping**

Start the server in the background, with the Step 3 exports: `.venv/bin/python manage.py runserver 127.0.0.1:8765 --insecure`. Then use the chrome-devtools tools (`new_page`, `resize_page`, `type_text`, `press_key`, `take_screenshot`, `evaluate_script`).

1. **Home at 1280×800.** Type `kay` in What. The popup lists kayak experiences with their places and prices. ArrowDown twice then Enter opens the second one. Esc closes the popup, and blur closes it too.
2. **Home at 390×844.** The hero card stacks What, Where, When and Search, with no Category field.
   - Tapping When opens the native date picker.
   - After a date is picked, the label reads e.g. `Sun 18 Oct`.
3. **`/bookings/?q=kayak` at 390×844.** There is one summary line, `kayak · All of Montenegro · Any date`.
   - Tapping it opens the full-screen panel with What focused.
   - Esc closes it and returns focus to the summary.
   - Submitting a new query from the panel works.
4. **`/bookings/?q=kayak+ulcinj`.** The page shows the no-match line, then "Close matches" with cards.
5. **`/bookings/?q=zzzz&date=<a future date>`.** The page shows the message naming both, the popular categories and Clear filters.
6. **`/sr/bookings/?date=<a future date>`.** The bar is in Serbian, the date label is in Latin script (`ned 18. okt`), and suggestion links start with `/sr/`.
7. **`/shop/?q=honey`.** The shop bar finds the honey.
8. **No sideways scroll.** On `/`, `/bookings/?q=kayak`, `/bookings/?q=zzzz` and `/shop/` at 390 px, `evaluate_script` of `() => document.documentElement.scrollWidth <= window.innerWidth` returns `true`.

Take a screenshot of 1 to 3 at each width. A defect found here is fixed with a test where one can pin it (a CSS-only defect: note the before/after screenshot in the ledger), then this step is repeated. Stop the server afterwards.

- [ ] **Step 6: Docs**

In `CLAUDE.md`, add after the paragraph that begins `**Convention — a vertical extends Product, and shopping surfaces list \`shoppable()\``:

```markdown
**Convention — the travel store's search is one engine (v0.112.0).** `booking_marketplace/search.py`
folds text (case, accents, Serbian Cyrillic, `đ` both ways) and ranks the active listings and
places from a per-process index; `/bookings/`, `/shop/` and `/bookings/suggest/` filter in the
database first (region, the category's subtree, `services.bookable_on` for a date) and let it rank
what survives — the index never decides what is live. It rebuilds when a listing, place or category
is saved or deleted (`search.bump`, a version token in the shared cache) and at the latest after
`MAX_AGE_S`, because `QuerySet.update()` skips the signal. A typo is tried only when a word matches
nothing as typed: on the live content, allowing one for every word brought the biking tours for
"hiking". Searches fire `SEARCH_PERFORMED` like the storefront's own; a script's JSON fetch is not a
pageview (analytics counts HTML pages only). Guarded by `booking_marketplace/tests/test_search_*.py`
and `test_bookable_on.py`.
```

In the i18n landmine paragraph (the one that begins `**Landmine — a translated URL tree whose links are plain paths`), append this sentence after `Auth (\`/auth/\`) is deliberately outside the language tree and stays English.`:

```markdown
Django's own `sr` catalog is Cyrillic: `|date` day and month names render "суб." and "Окт." on the Latin `/sr/` pages (the booking widget still does), so a visitor-facing date is formatted with Babel's `sr_Latn_ME` (`search_page.date_label`) and, in the browser, `Intl` with `sr-Latn-ME`.
```

In the spec, add under the title line `Design approved by the owner…` the line: `Status: shipped in v0.112.0 (2026-10-14).`

```bash
git add CLAUDE.md docs/superpowers/specs/2026-10-14-montenegro-search-design.md
git commit -m "docs: the travel store's search convention; Django's Serbian dates are Cyrillic" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Release**

```bash
DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py release --minor "Search finds what visitors type" \
  -m "On Montenegro, search matches every word in any order (“kayak kotor”), with or without accents or Cyrillic (zabljak, Жабљак), in Serbian (kajak) and with a typo (kayac), and shows the best match first." \
  -m "A date shows only the experiences with a seat left that day, and the category links in the menu find their experiences again." \
  -m "Suggestions appear as you type: experiences, places and categories." \
  -m "One search bar on the home page, the experiences and the shop; on a phone it folds into one line that opens full screen." \
  -m "The results page says what you searched for, with removable filters, close matches, and popular categories when nothing matches." \
  -m "Searches now show in search analytics, and suggestion requests no longer count as page views."
```

Then edit the new `## v0.112.0` entry in `docs/RELEASE_NOTES.md`. Under its bullets, add the table below, with one row per probe from Step 4: the "before" number from the table there, and the "after" number and first result from `$S/after.md`. The row shown is the shape, filled with the prototype's numbers; use the measured ones.

```markdown

| Search on montenegro-experience.me | Before | After (top result) |
|---|---|---|
| `kayak kotor` | 0 | 4 — Sunset Kayak Tour on the Bay of Kotor |
```

```bash
DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py release --check
git add morph/settings.py docs/RELEASE_NOTES.md
git commit -m "chore(release): v0.112.0 — Search finds what visitors type" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 8: Ship**

Merging to `main` deploys every store. The plan's approval covers this step.

```bash
git checkout main && git merge --ff-only feat/montenegro-search && git push origin main
SMOKE_DEADLINE_SECS=2400 scripts/deploy_smoke.sh v0.112.0
git branch -d feat/montenegro-search
```

Expected: the smoke script reports all stores on v0.112.0. If Coolify misses the webhook, force it as in the deploy-workflow memory (`POST /api/v1/deploy?uuid=…&force=true`).

- [ ] **Step 9: Verify live**

```bash
B=https://montenegro-experience.me
for q in 'kayak' 'kayak kotor' 'rafting tara' 'sunset budva' 'blue cave tivat' 'wine tasting podgorica' 'kajak' 'kayac' 'zabljak'; do
  printf '%s: ' "$q"; curl -s "$B/bookings/?q=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$q")&cb=$RANDOM" -H 'User-Agent: Mozilla/5.0 probe' \
    | python3 -c "import re,sys;b=sys.stdin.read();m=re.search(r'id=\"results-count\"[^>]*>([^<]*)<',b);c='close' if 'id=\"close-matches\"' in b else '';print((m.group(1).strip() if m else 'none'), c, re.findall(r'class=\"card-link\">([^<]+)<', b)[:2])"
done
curl -s "$B/bookings/?category=water-sports&cb=$RANDOM" | grep -o 'id="results-count"[^<]*<' | head -1
curl -sI "$B/bookings/suggest/?q=kay&cb=$RANDOM" | grep -iE '^(HTTP|x-robots-tag|cache-control|content-type)'
curl -s "$B/bookings/suggest/?q=kay&cb=$RANDOM" | python3 -m json.tool | head -30
curl -s "$B/sr/bookings/suggest/?q=kotor&cb=$RANDOM" | python3 -c "import json,sys; d=json.load(sys.stdin); print([i['url'] for g in d.values() for i in g][:6])"
```

Expected:
- the counts match `$S/after.md`
- `water-sports` shows 32 experiences
- the suggest headers are `200`, `x-robots-tag: noindex`, `cache-control: public, max-age=60` and `application/json`
- the Serbian links start with `/sr/`

Then repeat Step 5's items 1, 3 and 8 against the live site in the browser. Add `?cb=` to every URL, because Cloudflare caches HTML.

- [ ] **Step 10: Remember**

- Write the memory file `/Users/magnetoid/.claude/projects/-Users-magnetoid-coding-morph/memory/montenegro-search-v0112.md`. Include:
  - what shipped
  - the engine's rules: the typo rule, the stopwords, matching within the filters
  - where the index version lives
  - the analytics pageview fix
  - the Cyrillic date-names landmine
  - the live before/after numbers
  - follow-ups:
    - the booking widget's Cyrillic day and month names on `/sr/`
    - carrying the chosen date into the experience page
    - Serbian listing text (localization step 1)
- Add its line to `MEMORY.md`.
- Delete `$S/smoke.sqlite3`. `git status` should show only the untracked files that were there before.
