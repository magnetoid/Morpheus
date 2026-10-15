# Dotbooks Book Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dotbooks' `/products/` page gets five real filters (Genre, Topic, Author, Format, Length). Each takes several values and shows a count per choice, the sort menu gets three new orders, and on a phone the filters open in a bottom sheet.

**Architecture:**
- The book app answers a new hook filter, `LISTING_FACETS`. It narrows the product queryset and describes each facet with counts, taken with the other facets applied.
- The storefront view fires the filter and renders what comes back; it no longer reads book data itself.
- The dot_books theme renders a generic facet toolbar (`<details>` panels inside the GET form), and a small script adds apply-on-close, in-panel search and the phone sheet.

**Tech Stack:** Django 6.1, the Morpheus hook bus, the dot_books theme (Django templates plus vanilla JS), sqlite in-memory tests.

**Spec:** `docs/superpowers/specs/2026-10-16-dotbooks-book-filters-design.md`

## Global Constraints

- **Facets and their parameter values:**
  - The keys are `genre`, `topic`, `author`, `format` and `length`, as repeated query keys (`?genre=a&genre=b`).
  - Formats are `print`, `digital` and `audiobook`.
  - Lengths are `under-150`, `150-300`, `300-500` and `500-plus` (lower bound inclusive, upper bound exclusive).
  - The order is Genre, Topic, Author, Format, Length.
- **How facets combine:** values inside one facet are OR; facets are AND.
- **Counts:**
  - A facet's counts are taken with every OTHER facet applied, plus the storefront's own filters.
  - A choice with a count of 0 is not listed unless it is selected.
  - Topic lists choices with 2 or more books (`TOPIC_MIN_BOOKS = 2`), plus selected ones.
  - Genre is searchable only above 12 choices; Topic and Author are always searchable.
- **Format rule:**
  - A variant counts only when it is active.
  - An audiobook is a variant with `variant_type='audiobook'`, or a variant whose name contains "audio" (2 live audiobooks are typed `digital`).
  - Digital is `variant_type='digital'` with no "audio" in the name.
  - Print is `variant_type='physical'`, or a product with no variants.
- **Sorts:**
  - `newest` "Newest"
  - `name` "Title A–Z" (the key `name` stays, so old links keep working)
  - `author` "Author A–Z"
  - `price_asc` "Price ↑"
  - `price_desc` "Price ↓"
  - `shortest` "Shortest"
  - `longest` "Longest" (page count, nulls last)

  The book app supplies `author`, `shortest` and `longest`.
- **Default intro copy:** "Independent, modern, hand-curated. Filter by genre, topic, author, format or length. The shelf rotates every Tuesday."
- **No new plugin→plugin imports.** The storefront view stops importing `book_product`. The ratchets stay at core 0, plugin standard 38, and plugin boundary 113 or lower. If a storefront→book_product pair disappears, run `--save`, and the baseline shrinks.
- **The page's styles live in `{% block extra_head %}`, before the markup** (CLAUDE.md's CLS landmine).
- **Test command** (written as `$TEST` below): `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace' .venv/bin/python manage.py test`
- **Commits:**
  - end with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`;
  - stay local on `main` until Task 5.
- **Release:** v0.114.0 (`manage.py release --minor`). If Wave 1 ships first, use the next minor.

## Review Focus

1. **An old single-value link** (`/products/?author=Agatha%20Christie`, `?genre=mystery`, `?topic=love`) must still filter as before, keep its heading ("Books by Agatha Christie") and show its choice as selected. This is tested in Task 2.
2. **An author typed with different case** (`?author=agatha christie`) still matches, as the old `iexact` path did, and is shown selected. This is tested in Task 1.
3. **A product with both a PDF and an audiobook variant** counts under Digital AND Audiobook, and a Digital filter never drops it because of its audiobook variant. This is tested in Task 1.
4. **Pagination and chip links keep every repeated key** (`?genre=a&genre=b&page=2`). Removing one chip removes exactly that one value. This is tested in Task 2.
5. **A store without the book app** (Montenegro, Supernatural, Irving) ignores `genre`, `topic`, `author`, `format` and `length` without error, and renders no facets. This is tested in Task 2.

---

### Task 1: The book facets (`book_product/listing_facets.py`)

**Files:**
- Create: `plugins/installed/book_product/listing_facets.py`
- Test: `plugins/installed/book_product/tests/test_listing_facets.py`

**Interfaces:**
- Produces:
  - `selections(params) -> dict[str, list[str]]`, whose keys are exactly `FACET_KEYS`.
  - `apply(qs, chosen, *, skip: str | None = None) -> QuerySet`, a distinct queryset.
  - `describe(base_qs, chosen) -> list[dict]`. Each dict is `{'key', 'label', 'searchable', 'selected_count', 'options': [{'value', 'label', 'count', 'selected'}]}`.
  - `SORTS: tuple[tuple[str, str, tuple], ...]`, of `(key, label, order_by_args)`.
  - `answer(value: dict, params) -> dict`, the `LISTING_FACETS` handler body.
  - Constants: `FACET_KEYS`, `FORMATS`, `LENGTHS`, `TOPIC_MIN_BOOKS`.

- [ ] **Step 1: Write the failing test**

Create `plugins/installed/book_product/tests/test_listing_facets.py`:

```python
"""Book filters for the all-books page: what each facet narrows and counts.

Values inside one facet widen (OR); facets narrow each other (AND). A facet's
counts are taken with every OTHER facet applied, so a number next to a choice
says how many books that choice would leave.
"""

from __future__ import annotations

from decimal import Decimal

from django.http import QueryDict
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.listing_facets import (
    SORTS,
    answer,
    apply,
    describe,
    selections,
)
from plugins.installed.book_product.models import BookProduct, Genre, Topic
from plugins.installed.catalog.models import Product, ProductVariant


def _book(slug, *, author='', pages=None, genres=(), topics=(), variants=()):
    p = Product.objects.create(
        name=slug.replace('-', ' ').title(), slug=slug, sku=slug.upper(),
        price=Money(Decimal('9.00'), 'USD'),
        product_type='variable' if variants else 'simple', status='active',
    )
    b = BookProduct.objects.create(product=p, author=author, page_count=pages)
    b.genres.set(genres)
    b.topics.set(topics)
    for i, (name, vtype) in enumerate(variants):
        ProductVariant.objects.create(
            product=p, name=name, sku=f'{slug}-{i}', price=Money(Decimal('9.00'), 'USD'),
            variant_type=vtype,
        )
    return p


def _q(query: str) -> QueryDict:
    return QueryDict(query)


def _facet(facets, key):
    return next(f for f in facets if f['key'] == key)


def _counts(facet):
    return {o['value']: o['count'] for o in facet['options']}


class FacetFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fantasy = Genre.objects.create(name='Fantasy', slug='fantasy')
        cls.mystery = Genre.objects.create(name='Mystery', slug='mystery')
        cls.love = Topic.objects.create(name='Love', slug='love')
        cls.spies = Topic.objects.create(name='Espionage', slug='espionage')
        cls.once = Topic.objects.create(name='Lighthouses', slug='lighthouses')
        cls.a = _book('dragon', author='Ursula Le Guin', pages=120, genres=[cls.fantasy],
                      topics=[cls.love], variants=[('Print', 'physical'), ('Digital PDF', 'digital')])
        cls.b = _book('quest', author='Ursula Le Guin', pages=420, genres=[cls.fantasy],
                      topics=[cls.love, cls.spies], variants=[('Digital PDF', 'digital'), ('Audiobook', 'digital')])
        cls.c = _book('murder', author='Agatha Christie', pages=250, genres=[cls.mystery],
                      topics=[cls.spies, cls.once])
        cls.d = _book('notes', author='', pages=None, genres=[cls.mystery], topics=[cls.love])

    def base(self):
        return Product.objects.filter(status='active')


class SelectionTests(TestCase):
    def test_repeated_keys_become_lists_without_blanks_or_repeats(self):
        chosen = selections(_q('genre=a&genre=b&genre=a&genre=&topic=x&sort=name'))
        self.assertEqual(chosen['genre'], ['a', 'b'])
        self.assertEqual(chosen['topic'], ['x'])
        self.assertEqual(chosen['author'], [])
        self.assertEqual(set(chosen), {'genre', 'topic', 'author', 'format', 'length'})


class ApplyTests(FacetFixture):
    def _slugs(self, query):
        return set(apply(self.base(), selections(_q(query))).values_list('slug', flat=True))

    def test_values_inside_a_facet_widen(self):
        self.assertEqual(self._slugs('genre=fantasy&genre=mystery'), {'dragon', 'quest', 'murder', 'notes'})

    def test_facets_narrow_each_other(self):
        self.assertEqual(self._slugs('genre=fantasy&topic=espionage'), {'quest'})

    def test_author_matches_ignoring_case(self):
        self.assertEqual(self._slugs('author=agatha%20christie'), {'murder'})

    def test_length_buckets_and_books_without_a_page_count(self):
        self.assertEqual(self._slugs('length=under-150'), {'dragon'})
        self.assertEqual(self._slugs('length=150-300&length=300-500'), {'murder', 'quest'})
        self.assertNotIn('notes', self._slugs('length=under-150&length=150-300&length=300-500&length=500-plus'))

    def test_format_rules(self):
        self.assertEqual(self._slugs('format=print'), {'dragon', 'murder', 'notes'})
        self.assertEqual(self._slugs('format=digital'), {'dragon', 'quest'})
        self.assertEqual(self._slugs('format=audiobook'), {'quest'})

    def test_an_unknown_value_narrows_to_nothing_not_everything(self):
        self.assertEqual(self._slugs('genre=no-such-genre'), set())

    def test_an_unknown_format_or_length_is_ignored(self):
        self.assertEqual(len(self._slugs('format=vinyl')), 4)
        self.assertEqual(len(self._slugs('length=huge')), 4)


class DescribeTests(FacetFixture):
    def test_counts_ignore_the_facets_own_choice(self):
        facets = describe(self.base(), selections(_q('genre=fantasy')))
        self.assertEqual(_counts(_facet(facets, 'genre')), {'fantasy': 2, 'mystery': 2})
        # Another facet's counts are narrowed by the chosen genre.
        self.assertEqual(_counts(_facet(facets, 'author')), {'Ursula Le Guin': 2})

    def test_a_choice_that_leaves_nothing_is_hidden_unless_selected(self):
        facets = describe(self.base(), selections(_q('genre=mystery&format=audiobook')))
        # Genre counts ignore the chosen genre: the one audiobook is a fantasy book.
        # Mystery leaves nothing with audiobook, but it is selected, so it stays at 0.
        self.assertEqual(_counts(_facet(facets, 'genre')), {'fantasy': 1, 'mystery': 0})
        # Format counts ignore the chosen format: the two mystery books are print only.
        # Digital leaves nothing and isn't selected, so it is hidden.
        self.assertEqual(_counts(_facet(facets, 'format')), {'print': 2, 'audiobook': 0})

    def test_a_topic_with_one_book_is_not_listed(self):
        topics = _counts(_facet(describe(self.base(), selections(_q(''))), 'topic'))
        self.assertEqual(topics, {'love': 3, 'espionage': 2})

    def test_a_selected_author_typed_in_another_case_is_shown_selected(self):
        author = _facet(describe(self.base(), selections(_q('author=agatha%20christie'))), 'author')
        chosen = [o for o in author['options'] if o['selected']]
        self.assertEqual([o['value'] for o in chosen], ['Agatha Christie'])

    def test_order_labels_and_search(self):
        facets = describe(self.base(), selections(_q('')))
        self.assertEqual([f['key'] for f in facets], ['genre', 'topic', 'author', 'format', 'length'])
        self.assertTrue(_facet(facets, 'topic')['searchable'])
        self.assertTrue(_facet(facets, 'author')['searchable'])
        self.assertFalse(_facet(facets, 'genre')['searchable'])
        self.assertEqual([o['label'] for o in _facet(facets, 'format')['options']], ['Print', 'Digital PDF', 'Audiobook'])
        self.assertEqual(_counts(_facet(facets, 'length')), {'under-150': 1, '150-300': 1, '300-500': 1})


class AnswerTests(FacetFixture):
    def test_the_hook_answer_narrows_and_describes(self):
        out = answer({'queryset': self.base(), 'facets': [], 'sorts': [], 'chosen': {}}, _q('genre=mystery'))
        self.assertEqual(set(out['queryset'].values_list('slug', flat=True)), {'murder', 'notes'})
        self.assertEqual(out['chosen'], {'genre': ['mystery']})
        self.assertEqual([s[0] for s in out['sorts']], [s[0] for s in SORTS])
        self.assertEqual(len(out['facets']), 5)

    def test_sorts_by_author_and_length(self):
        by_author = dict((k, o) for k, _l, o in SORTS)
        names = list(self.base().order_by(*by_author['author']).values_list('slug', flat=True))
        self.assertEqual(names[:3], ['notes', 'murder', 'dragon'])
        shortest = list(self.base().order_by(*by_author['shortest']).values_list('slug', flat=True))
        self.assertEqual(shortest, ['dragon', 'murder', 'quest', 'notes'])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `$TEST plugins.installed.book_product.tests.test_listing_facets`
Expected: ERROR, `ModuleNotFoundError: No module named 'plugins.installed.book_product.listing_facets'`.

- [ ] **Step 3: Create `plugins/installed/book_product/listing_facets.py`**

```python
"""The book filters on the all-books page: genre, topic, author, format, length.

Answers `LISTING_FACETS` for the storefront's product list (spec
docs/superpowers/specs/2026-10-16-dotbooks-book-filters-design.md). Values
inside one facet widen (OR); facets narrow each other (AND). Each facet's
counts are taken with every OTHER facet applied, so a count says how many books
that choice would leave.
"""

from __future__ import annotations

from django.db.models import Count, F, Q

FACET_KEYS = ('genre', 'topic', 'author', 'format', 'length')
FORMATS = (('print', 'Print'), ('digital', 'Digital PDF'), ('audiobook', 'Audiobook'))
# (value, label, lowest page count included, first page count excluded)
LENGTHS = (
    ('under-150', 'Under 150 pages', None, 150),
    ('150-300', '150–300 pages', 150, 300),
    ('300-500', '300–500 pages', 300, 500),
    ('500-plus', '500+ pages', 500, None),
)
TOPIC_MIN_BOOKS = 2
GENRE_SEARCH_ABOVE = 12
SORTS = (
    ('author', 'Author A–Z', ('book__author', 'name')),
    ('shortest', 'Shortest', (F('book__page_count').asc(nulls_last=True), 'name')),
    ('longest', 'Longest', (F('book__page_count').desc(nulls_last=True), 'name')),
)


def selections(params) -> dict[str, list[str]]:
    """Each facet's chosen values from repeated query keys; blanks and repeats dropped."""
    chosen: dict[str, list[str]] = {}
    for key in FACET_KEYS:
        values: list[str] = []
        for raw in params.getlist(key) if params is not None else []:
            value = (raw or '').strip()
            if value and value not in values:
                values.append(value)
        chosen[key] = values
    return chosen


def _variant_products(**kw):
    from plugins.installed.catalog.models import ProductVariant

    return ProductVariant.objects.filter(is_active=True, **kw)


def _format_q(value: str) -> Q | None:
    audio = Q(variant_type='audiobook') | Q(name__icontains='audio')
    if value == 'audiobook':
        return Q(pk__in=_variant_products().filter(audio).values('product_id'))
    if value == 'digital':
        return Q(
            pk__in=_variant_products(variant_type='digital')
            .exclude(name__icontains='audio')
            .values('product_id')
        )
    if value == 'print':
        return Q(pk__in=_variant_products(variant_type='physical').values('product_id')) | Q(
            variants__isnull=True
        )
    return None


def _length_q(value: str) -> Q | None:
    row = next((r for r in LENGTHS if r[0] == value), None)
    if row is None:
        return None
    _value, _label, low, high = row
    cond = Q(book__page_count__isnull=False)
    if low is not None:
        cond &= Q(book__page_count__gte=low)
    if high is not None:
        cond &= Q(book__page_count__lt=high)
    return cond


def _facet_q(key: str, values: list[str]) -> Q | None:
    """The OR of a facet's values, or None when no value means anything."""
    if key == 'genre':
        return Q(book__genres__slug__in=values)
    if key == 'topic':
        return Q(book__topics__slug__in=values)
    if key == 'author':
        q = Q()
        for v in values:
            q |= Q(book__author__iexact=v)
        return q
    builder = _format_q if key == 'format' else _length_q
    parts = [p for p in (builder(v) for v in values) if p is not None]
    if not parts:
        return None
    q = parts[0]
    for p in parts[1:]:
        q |= p
    return q


def apply(qs, chosen: dict, *, skip: str | None = None):
    """Narrow `qs` by every chosen facet except `skip`."""
    for key in FACET_KEYS:
        values = chosen.get(key) or []
        if key == skip or not values:
            continue
        q = _facet_q(key, values)
        if q is not None:
            qs = qs.filter(q)
    return qs.distinct()


def _scope(base_qs, chosen, key):
    from plugins.installed.catalog.models import Product

    ids = apply(base_qs, chosen, skip=key).order_by().values('pk')
    return Product.objects.filter(pk__in=ids)


def _options(rows, selected: list[str], *, fold=False):
    """rows: [(value, label, count)] → option dicts; zero counts dropped unless selected;
    a selected value with no row is added with count 0."""
    picked = {s.lower() for s in selected} if fold else set(selected)
    out, seen = [], set()
    for value, label, count in rows:
        is_sel = (value.lower() if fold else value) in picked
        if count or is_sel:
            out.append({'value': value, 'label': label, 'count': count, 'selected': is_sel})
            seen.add(value.lower() if fold else value)
    for s in selected:
        if (s.lower() if fold else s) not in seen:
            out.append({'value': s, 'label': s, 'count': 0, 'selected': True})
    return out


def _taxonomy_rows(model, scope, *, min_books=1):
    rows = (
        model.objects.filter(is_active=True, books__product__in=scope)
        .annotate(n=Count('books', distinct=True))
        .filter(n__gte=min_books)
        .order_by('-n', 'name')
    )
    return [(t.slug, t.name, t.n) for t in rows]


def _facet(key, label, options, *, searchable=False):
    return {
        'key': key,
        'label': label,
        'searchable': searchable,
        'selected_count': sum(1 for o in options if o['selected']),
        'options': options,
    }


def describe(base_qs, chosen: dict) -> list[dict]:
    """Every facet with its options and counts; a facet with no options is left out."""
    from plugins.installed.book_product.models import BookProduct, Genre, Topic

    facets = []

    def labelled(model, values):
        names = dict(model.objects.filter(slug__in=values).values_list('slug', 'name'))
        return names

    genre_opts = _options(_taxonomy_rows(Genre, _scope(base_qs, chosen, 'genre')), chosen['genre'])
    names = labelled(Genre, [o['value'] for o in genre_opts if o['count'] == 0])
    for o in genre_opts:
        o['label'] = names.get(o['value'], o['label'])
    facets.append(_facet('genre', 'Genre', genre_opts, searchable=len(genre_opts) > GENRE_SEARCH_ABOVE))

    topic_opts = _options(
        _taxonomy_rows(Topic, _scope(base_qs, chosen, 'topic'), min_books=TOPIC_MIN_BOOKS),
        chosen['topic'],
    )
    names = labelled(Topic, [o['value'] for o in topic_opts if o['count'] == 0])
    for o in topic_opts:
        o['label'] = names.get(o['value'], o['label'])
    facets.append(_facet('topic', 'Topic', topic_opts, searchable=True))

    authors = (
        BookProduct.objects.filter(product__in=_scope(base_qs, chosen, 'author'))
        .exclude(author='')
        .values('author')
        .annotate(n=Count('product', distinct=True))
        .order_by('author')
    )
    author_opts = _options([(r['author'], r['author'], r['n']) for r in authors], chosen['author'], fold=True)
    facets.append(_facet('author', 'Author', author_opts, searchable=True))

    scope = _scope(base_qs, chosen, 'format')
    fmt_rows = [(v, label, scope.filter(_format_q(v)).distinct().count()) for v, label in FORMATS]
    facets.append(_facet('format', 'Format', _options(fmt_rows, chosen['format'])))

    scope = _scope(base_qs, chosen, 'length')
    len_rows = [(v, label, scope.filter(_length_q(v)).count()) for v, label, _lo, _hi in LENGTHS]
    facets.append(_facet('length', 'Length', _options(len_rows, chosen['length'])))

    return [f for f in facets if f['options']]


def answer(value: dict, params) -> dict:
    """LISTING_FACETS: narrow the listing by the book facets and describe them."""
    if not isinstance(value, dict) or value.get('queryset') is None or params is None:
        return value
    chosen = selections(params)
    base = value['queryset']
    value['queryset'] = apply(base, chosen)
    value['facets'] = list(value.get('facets') or []) + describe(base, chosen)
    value['sorts'] = list(value.get('sorts') or []) + list(SORTS)
    value['chosen'] = {**(value.get('chosen') or {}), **{k: v for k, v in chosen.items() if v}}
    return value
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `$TEST plugins.installed.book_product.tests.test_listing_facets`
Expected: OK. If `test_sorts_by_author_and_length` fails only on how sqlite orders an empty author, assert on the books with authors instead and ledger the change.

- [ ] **Step 5: Commit**

```bash
git add plugins/installed/book_product/listing_facets.py plugins/installed/book_product/tests/test_listing_facets.py
git commit -m "feat(books): genre, topic, author, format and length facets with counts

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: The `LISTING_FACETS` seam in the storefront view

**Files:**
- Modify:
  - `core/hooks.py` (constant after `PRODUCT_LIST_REORDER`, ~line 524)
  - `plugins/installed/book_product/app.py` (`ready()` + handler)
  - `plugins/installed/storefront/views/catalog.py` (`product_list`)
- Test: `plugins/installed/storefront/tests/test_listing_facets_seam.py`

**Interfaces:**
- Consumes: `listing_facets.answer` (Task 1).
- Produces: the context keys used by Task 3's template:
  - `listing_facets` (list of facet dicts)
  - `listing_sorts` (list of `(key, label)`)
  - `filter_chips` (list of `{'label', 'href'}`)
  - `chosen_count` (int)
  - `result_count` (int)
  - `selected_author` (str; set only when exactly one author is chosen and no other book facet)
  - `selected_genre_label` (str; same rule for genre)

  It also produces `MorpheusEvents.LISTING_FACETS = 'listing.facets'`.

- [ ] **Step 1: Write the failing test**

Create `plugins/installed/storefront/tests/test_listing_facets_seam.py`:

```python
"""The all-books page asks the book app for its filters (LISTING_FACETS).

The storefront used to filter `book__genres__slug` and import book_product for
authors itself; now it fires one filter and renders what comes back, so a store
without the book app simply has no book filters.
"""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import parse_qs

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct, Genre
from plugins.installed.catalog.models import Product
from plugins.registry import app_registry


def _book(slug, author, genres=()):
    p = Product.objects.create(
        name=slug.title(), slug=slug, sku=slug.upper(), price=Money(Decimal('9.00'), 'USD'),
        product_type='simple', status='active',
    )
    b = BookProduct.objects.create(product=p, author=author, page_count=200)
    b.genres.set(genres)
    return p


class SeamTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mystery = Genre.objects.create(name='Mystery', slug='mystery')
        cls.poetry = Genre.objects.create(name='Poetry', slug='poetry')
        _book('murder', 'Agatha Christie', [cls.mystery])
        _book('verses', 'Emily Dickinson', [cls.poetry])
        _book('tea', 'Agatha Christie', [cls.poetry])

    def _ctx(self, query=''):
        resp = self.client.get(f'/products/{query}')
        self.assertEqual(resp.status_code, 200)
        return resp.context

    def _slugs(self, ctx):
        return {p.slug for p in ctx['products']}

    def test_the_view_uses_the_queryset_the_book_app_returns(self):
        ctx = self._ctx('?genre=mystery&genre=poetry&author=Agatha%20Christie')
        self.assertEqual(self._slugs(ctx), {'murder', 'tea'})
        self.assertTrue(ctx['listing_facets'])
        self.assertEqual(ctx['result_count'], 2)
        self.assertEqual(ctx['chosen_count'], 3)

    def test_old_single_value_links_keep_their_heading(self):
        ctx = self._ctx('?author=Agatha%20Christie')
        self.assertEqual(self._slugs(ctx), {'murder', 'tea'})
        self.assertEqual(ctx['selected_author'], 'Agatha Christie')
        self.assertEqual(ctx['plp_name'], 'Books by Agatha Christie')
        ctx = self._ctx('?genre=mystery')
        self.assertEqual(ctx['selected_genre_label'], 'Mystery')

    def test_a_chip_removes_exactly_its_value_and_keeps_the_rest(self):
        ctx = self._ctx('?genre=mystery&genre=poetry&sort=name&page=1')
        chip = next(c for c in ctx['filter_chips'] if c['label'] == 'Genre: Mystery')
        self.assertEqual(parse_qs(chip['href'].lstrip('?')), {'genre': ['poetry'], 'sort': ['name']})

    def test_pagination_keeps_repeated_keys(self):
        ctx = self._ctx('?genre=mystery&genre=poetry')
        self.assertEqual(parse_qs(ctx['paginator_base_qs']), {'genre': ['mystery', 'poetry']})

    def test_book_sorts_are_offered(self):
        keys = [k for k, _l in self._ctx()['listing_sorts']]
        self.assertEqual(keys, ['newest', 'name', 'author', 'price_asc', 'price_desc', 'shortest', 'longest'])

    def test_without_the_book_app_the_parameters_are_ignored_and_no_facets_render(self):
        self.addCleanup(app_registry.activate, 'book_product')
        app_registry.deactivate('book_product')
        ctx = self._ctx('?genre=mystery&author=Nobody&format=print&length=500-plus')
        self.assertEqual(self._slugs(ctx), {'murder', 'verses', 'tea'})
        self.assertEqual(ctx['listing_facets'], [])
        self.assertEqual([k for k, _l in ctx['listing_sorts']], ['newest', 'name', 'price_asc', 'price_desc'])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `$TEST plugins.installed.storefront.tests.test_listing_facets_seam`
Expected: FAIL or ERROR with `KeyError: 'listing_facets'` (the context lacks the new keys), and the multi-value genre returns too few products.

- [ ] **Step 3: Add the event (`core/hooks.py`)**

After the line `PRODUCT_LIST_REORDER = 'product.list.reorder'  # filter`, insert:

```python

    # LISTING_FACETS — filter, value={'queryset': QuerySet[Product], 'facets': list,
    #   'sorts': list, 'chosen': dict}, kwargs: params (the request's QueryDict),
    #   surface ('product_list'). Fired by the storefront's product list after its
    #   own filters, before sorting and pagination. An app that owns product data
    #   (book_product: genre, topic, author, format, length) narrows `queryset`,
    #   appends facet dicts ({'key','label','searchable','selected_count',
    #   'options':[{'value','label','count','selected'}]}), extra sorts
    #   ((key, label, order_by_args)) and its chosen values. Nothing answers on a
    #   store without such an app, and the page shows no extra filters.
    LISTING_FACETS = 'listing.facets'  # filter
```

- [ ] **Step 4: The book app answers (`plugins/installed/book_product/app.py`)**

In `ready()`, after `self.register_hook(events.SEO_RESOLVE_PAGE, self.on_seo_resolve_page, priority=40)`, add:

```python
        # The all-books page's genre/topic/author/format/length filters.
        self.register_hook(events.LISTING_FACETS, self.on_listing_facets, priority=40)
```

Add this method to the plugin class:

```python
    def on_listing_facets(self, value, params=None, surface='', **_):
        from plugins.installed.book_product.listing_facets import answer

        return answer(value, params)
```

- [ ] **Step 5: The view fires it (`plugins/installed/storefront/views/catalog.py`)**

1. **Delete the genre/topic block.** That is the block from `# Genre / Topic filter — ` through `qs = qs.filter(book__topics__slug=topic_slug).distinct()`.
2. **Keep only `publisher` in the book filter.** Replace the loop

   ```python
       for qk in ('author', 'publisher'):
   ```

   with

   ```python
       for qk in ('publisher',):
   ```

   The author filter now comes from LISTING_FACETS. `publisher` keeps its compat path for old links.
3. **Fire the hook.** Directly after `qs = qs.distinct()` (before `# Sort`), insert:

   ```python
       # Filters other apps own (the book app: genre, topic, author, format, length).
       listing = hook_registry.filter(
           MorpheusEvents.LISTING_FACETS,
           {'queryset': qs, 'facets': [], 'sorts': [], 'chosen': {}},
           params=request.GET,
           surface='product_list',
       )
       if not isinstance(listing, dict) or listing.get('queryset') is None:
           listing = {'queryset': qs, 'facets': [], 'sorts': [], 'chosen': {}}
       qs = listing['queryset']
       listing_facets = listing.get('facets') or []
       chosen_facets = listing.get('chosen') or {}
   ```

4. **Replace the sort block** (from `sort = (request.GET.get('sort') or 'for_you').strip()` through `qs = qs.order_by(sort_map.get(sort, '-created_at'))`) with:

   ```python
       sort = (request.GET.get('sort') or 'for_you').strip()
       sort_map = {
           'for_you': ('-created_at',),  # Base sort, dynamically reordered later
           'newest': ('-created_at',),
           'oldest': ('created_at',),
           'price_asc': ('price',),
           'price_desc': ('-price',),
           'name': ('name',),
       }
       extra_sorts = [s for s in listing.get('sorts') or [] if len(s) == 3]
       for key, _label, order in extra_sorts:
           sort_map[key] = tuple(order)
       qs = qs.order_by(*sort_map.get(sort, ('-created_at',)))
       listing_sorts = [('newest', gettext('Newest')), ('name', gettext('Title A–Z'))]
       listing_sorts += [(k, label) for k, label, _o in extra_sorts if k == 'author']
       listing_sorts += [('price_asc', gettext('Price ↑')), ('price_desc', gettext('Price ↓'))]
       listing_sorts += [(k, label) for k, label, _o in extra_sorts if k != 'author']
   ```

5. **Remove the datalist query.** Delete the `# Author facet — distinct authors …` block (`available_authors` and its try/except) and the `'available_authors': available_authors,` context line.
6. **Derive the heading and the chips from the facets.** Directly before the `_author_label = book_filter.get('author', '')` line, insert:

   ```python
       def _single(key):
           """The one chosen value of `key` when it is the only book facet chosen."""
           values = chosen_facets.get(key) or []
           others = [k for k, v in chosen_facets.items() if v and k != key]
           if len(values) != 1 or others:
               return ''
           facet = next((f for f in listing_facets if f['key'] == key), None)
           option = next((o for o in (facet or {}).get('options', []) if o['selected']), None)
           return option['label'] if option else values[0]

       selected_author = _single('author')
       selected_genre_label = _single('genre')

       def _without(key, value):
           q = request.GET.copy()
           q.pop('page', None)
           q.setlist(key, [v for v in q.getlist(key) if v != value])
           encoded = q.urlencode()
           return f'?{encoded}' if encoded else '/products/'

       filter_chips = [
           {'label': f'{f["label"]}: {o["label"]}', 'href': _without(f['key'], o['value'])}
           for f in listing_facets
           for o in f['options']
           if o['selected']
       ]
       chosen_count = len(filter_chips)
   ```

   Then change `_author_label = book_filter.get('author', '')` to `_author_label = selected_author`. In the heading chain, after the `elif _publisher_label:` branch, add:

   ```python
       elif selected_genre_label:
           plp_name = selected_genre_label
   ```

7. **`_is_filtered`.** Replace `or genre_slug` and `or topic_slug` with `or chosen_facets`. Keep `or book_filter` (publisher).
8. **Context.** Change `'selected_author': book_filter.get('author', ''),` to `'selected_author': selected_author,`. Add:

   ```python
               'selected_genre_label': selected_genre_label,
               'listing_facets': listing_facets,
               'listing_sorts': listing_sorts,
               'filter_chips': filter_chips,
               'chosen_count': chosen_count,
               'result_count': paginator.count,
   ```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `$TEST plugins.installed.storefront.tests.test_listing_facets_seam plugins.installed.book_product plugins.installed.storefront themes`
Expected: OK.

An existing storefront or theme test may assert the old author datalist or `genre_slug` behaviour. Update it to the facet behaviour only when its subject is the toolbar, and ledger each such update as a ruling.

Run: `.venv/bin/python scripts/check_plugin_boundary.py`
Expected: OK. If it reports a stale storefront→book_product pair (this task removed the `compat.distinct_values` import), run `--save` and include the shrunk baseline in the commit.

- [ ] **Step 7: Commit**

```bash
git add core/hooks.py plugins/installed/book_product/app.py plugins/installed/storefront/views/catalog.py plugins/installed/storefront/tests/test_listing_facets_seam.py scripts/plugin_boundary_baseline.json
git commit -m "feat(storefront): the all-books page takes its book filters from LISTING_FACETS

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: The dot_books filter toolbar, panels and phone sheet

**Files:**
- Create:
  - `themes/library/dot_books/templates/storefront/_listing_filters.html`
  - `themes/library/dot_books/static/dot_books/listing-filters.js`
- Modify: `themes/library/dot_books/templates/storefront/product_list.html`
- Test: `themes/test_dot_books_listing_filters.py`

**Interfaces:**
- Consumes: Task 2's context keys `listing_facets`, `listing_sorts`, `filter_chips`, `chosen_count`, `result_count`, `selected_author`, `selected_genre_label`, `selected_sort`, `search_query`, `selected_category`, `selected_tag`, `selected_publisher`, `facets`.

**Ruling carried from planning.** The spec's phone sheet button reads "Show N books". N would have to change as boxes are ticked, which needs a request per tick. The button reads "Show results" instead, and the count stays visible above the grid.

- [ ] **Step 1: Write the failing test**

Create `themes/test_dot_books_listing_filters.py`:

```python
"""dot_books' all-books toolbar renders the book filters as panels of checkboxes.

Each filter is a <details> panel inside the one GET form, so without JavaScript
ticking boxes and pressing Apply submits repeated keys; listing-filters.js adds
apply-on-close, in-panel search and the phone sheet.
"""

from __future__ import annotations

from decimal import Decimal

from django.template.loader import get_template
from django.test import TestCase
from djmoney.money import Money

from themes.test_head_contract import _activate_theme


class DotBooksListingFiltersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.book_product.models import BookProduct, Genre, Topic
        from plugins.installed.catalog.models import Product

        cls.mystery = Genre.objects.create(name='Mystery', slug='mystery')
        love = Topic.objects.create(name='Love', slug='love')
        for i, author in enumerate(['Agatha Christie', 'Agatha Christie', 'Emily Brontë']):
            p = Product.objects.create(
                name=f'Book {i}', slug=f'book-{i}', sku=f'BK-{i}',
                price=Money(Decimal('9.00'), 'USD'), product_type='simple', status='active',
            )
            b = BookProduct.objects.create(product=p, author=author, page_count=200 + i)
            b.genres.set([cls.mystery])
            b.topics.set([love])

    def setUp(self):
        _activate_theme(self, 'dot_books')

    def _page(self, query=''):
        resp = self.client.get(f'/products/{query}')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_the_partial_compiles(self):
        get_template('storefront/_listing_filters.html')

    def test_every_facet_is_a_panel_of_named_checkboxes_with_counts(self):
        html = self._page()
        for key in ('genre', 'topic', 'author', 'format', 'length'):
            self.assertIn(f'data-facet="{key}"', html)
        self.assertIn('name="genre" value="mystery"', html)
        self.assertIn('<span class="plp-option-count">3</span>', html)
        self.assertIn('data-panel-search', html)  # topic and author
        self.assertIn("dot_books/listing-filters.js", html)

    def test_chosen_values_are_checked_and_shown_as_removable_chips(self):
        html = self._page('?author=Agatha%20Christie&genre=mystery')
        self.assertIn('name="author" value="Agatha Christie" checked', html)
        self.assertIn('Author: Agatha Christie', html)
        self.assertIn('Clear all', html)

    def test_the_sort_menu_has_the_book_orders(self):
        html = self._page()
        for label in ('Newest', 'Title A–Z', 'Author A–Z', 'Price ↑', 'Price ↓', 'Shortest', 'Longest'):
            self.assertIn(label, html)

    def test_the_intro_no_longer_promises_a_publisher_filter(self):
        html = self._page()
        self.assertIn('Filter by genre, topic, author, format or length.', html)
        self.assertNotIn('Filter by genre or publisher', html)

    def test_the_old_author_box_is_gone(self):
        self.assertNotIn('plp-author-list', self._page())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `$TEST themes.test_dot_books_listing_filters`
Expected: FAIL/ERROR. `TemplateDoesNotExist: storefront/_listing_filters.html`, `data-facet` is missing, and the old intro copy is found.

- [ ] **Step 3: Create the partial `themes/library/dot_books/templates/storefront/_listing_filters.html`**

```django
{% load static i18n %}
{% comment %}
  The all-books toolbar (spec 2026-10-16-dotbooks-book-filters). One GET form: search,
  one <details> panel per facet from `listing_facets` (contributed through
  LISTING_FACETS), the sort menu, and Apply. Without JavaScript the panels open and
  close natively and Apply submits repeated keys; listing-filters.js applies a panel
  when it closes, narrows long lists as you type, and turns the facets into a bottom
  sheet under 720px.
{% endcomment %}
<form method="get" action="/products/" class="plp-toolbar" data-listing-filters>
  <div class="plp-search">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m21 21-4.3-4.3"></path></svg>
    <input name="q" value="{{ search_query }}" placeholder="{% trans 'Search by title or author' %}" aria-label="{% trans 'Search by title or author' %}">
  </div>
  {% if listing_facets %}
  <button type="button" class="plp-sheet-open btn" data-sheet-open hidden>{% trans 'Filters' %}{% if chosen_count %} ({{ chosen_count }}){% endif %}</button>
  <div class="plp-facets" data-sheet>
    <div class="plp-sheet-head">
      <strong>{% trans 'Filters' %}</strong>
      <button type="button" class="plp-sheet-close" data-sheet-close aria-label="{% trans 'Close filters' %}">✕</button>
    </div>
    {% for f in listing_facets %}
    <details class="plp-facet" data-facet="{{ f.key }}">
      <summary class="plp-facet-button">{{ f.label }}{% if f.selected_count %} <span class="plp-facet-n">· {{ f.selected_count }}</span>{% endif %}</summary>
      <div class="plp-panel" role="group" aria-label="{{ f.label }}">
        {% if f.searchable %}<input type="search" class="plp-panel-search" placeholder="{% blocktrans with label=f.label|lower %}Find {{ label }}…{% endblocktrans %}" aria-label="{% blocktrans with label=f.label|lower %}Find {{ label }}{% endblocktrans %}" data-panel-search>{% endif %}
        <div class="plp-options">
          {% for o in f.options %}
          <label class="plp-option"><input type="checkbox" name="{{ f.key }}" value="{{ o.value }}"{% if o.selected %} checked{% endif %}><span class="plp-option-label">{{ o.label }}</span><span class="plp-option-count">{{ o.count }}</span></label>
          {% endfor %}
        </div>
        <p class="plp-panel-empty" data-panel-empty hidden>{% trans 'Nothing matches.' %}</p>
      </div>
    </details>
    {% endfor %}
    <button class="btn btn-primary plp-sheet-apply" type="submit">{% trans 'Show results' %}</button>
  </div>
  {% endif %}
  <select name="sort" aria-label="{% trans 'Sort books' %}" class="plp-sort" onchange="this.form.requestSubmit()">
    {% for key, label in listing_sorts %}
    <option value="{{ key }}"{% if key == selected_sort %} selected{% endif %}>{{ label }}</option>
    {% endfor %}
  </select>
  {% if selected_category %}<input type="hidden" name="category" value="{{ selected_category }}">{% endif %}
  {% if selected_tag %}<input type="hidden" name="tag" value="{{ selected_tag }}">{% endif %}
  {% if selected_publisher %}<input type="hidden" name="publisher" value="{{ selected_publisher }}">{% endif %}
  {% for f in facets %}{% for v in f.selected %}<input type="hidden" name="attr_{{ f.attr.slug }}" value="{{ v }}">{% endfor %}{% endfor %}
  <button class="btn btn-primary plp-apply">{% trans 'Apply' %}</button>
</form>
<script src="{% static 'dot_books/listing-filters.js' %}" defer></script>
```

- [ ] **Step 4: Create `themes/library/dot_books/static/dot_books/listing-filters.js`**

```javascript
/* dot_books all-books filters: apply a panel when it closes, one panel open at a
   time, type-to-narrow inside long panels, and a bottom sheet under 720px.
   Without this file the form still works: <details> panels + the Apply button. */
(function () {
  var form = document.querySelector('[data-listing-filters]');
  if (!form) return;
  form.classList.add('js-filters');
  var panels = Array.prototype.slice.call(form.querySelectorAll('.plp-facet'));
  var sheetOpen = form.querySelector('[data-sheet-open]');
  var sheetClose = form.querySelector('[data-sheet-close]');
  var phone = window.matchMedia('(max-width: 720px)');

  function snapshot(panel) {
    return Array.prototype.map.call(
      panel.querySelectorAll('input[type=checkbox]:checked'),
      function (i) { return i.value; }
    ).join('\u0000');
  }
  function fold(s) {
    return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }

  panels.forEach(function (panel) {
    var before = snapshot(panel);
    panel.addEventListener('toggle', function () {
      if (panel.open) {
        panels.forEach(function (p) { if (p !== panel) p.open = false; });
        before = snapshot(panel);
        var search = panel.querySelector('[data-panel-search]');
        if (search && !phone.matches) search.focus();
      } else if (!phone.matches && snapshot(panel) !== before) {
        form.requestSubmit();
      }
    });
    var search = panel.querySelector('[data-panel-search]');
    if (search) {
      search.addEventListener('input', function () {
        var needle = fold(search.value.trim());
        var shown = 0;
        panel.querySelectorAll('.plp-option').forEach(function (opt) {
          var hit = !needle || fold(opt.textContent).indexOf(needle) !== -1;
          opt.hidden = !hit;
          if (hit) shown += 1;
        });
        var empty = panel.querySelector('[data-panel-empty]');
        if (empty) empty.hidden = shown !== 0;
      });
      search.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') e.preventDefault();
      });
    }
  });

  document.addEventListener('click', function (e) {
    if (phone.matches) return;
    panels.forEach(function (p) { if (p.open && !p.contains(e.target)) p.open = false; });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var open = panels.filter(function (p) { return p.open; })[0];
    if (open) {
      open.open = false;
      open.querySelector('summary').focus();
    } else if (form.classList.contains('sheet-open')) {
      closeSheet();
    }
  });

  function openSheet() {
    form.classList.add('sheet-open');
    document.body.style.overflow = 'hidden';
    if (sheetClose) sheetClose.focus();
  }
  function closeSheet() {
    form.classList.remove('sheet-open');
    document.body.style.overflow = '';
    if (sheetOpen) sheetOpen.focus();
  }
  if (sheetOpen) {
    sheetOpen.hidden = false;
    sheetOpen.addEventListener('click', openSheet);
  }
  if (sheetClose) sheetClose.addEventListener('click', closeSheet);
})();
```

- [ ] **Step 5: Wire it into `product_list.html`**
  1. **Styles in `{% block extra_head %}`.** After the `{% dl_view_item_list … %}` line, add the style block below. Delete the old `<style>` that follows the toolbar form (the one defining `.plp-count` / `.plp-toolbar`), and the old chip `<style>`.

  ```html
  <style>
    .plp-count { margin: 0.75rem 0 0; }
    .plp-toolbar { position: sticky; top: 64px; z-index: 20; display: flex; flex-wrap: wrap; gap: .6rem; align-items: center; margin-top: 2rem; padding: .75rem .25rem; margin-left: -.25rem; margin-right: -.25rem; background: color-mix(in srgb, var(--paper) 92%, transparent); backdrop-filter: blur(10px); }
    .plp-search { position: relative; flex: 1; min-width: 220px; max-width: 420px; }
    .plp-search svg { position: absolute; left: 1rem; top: 50%; transform: translateY(-50%); color: var(--muted); }
    .plp-search input { width: 100%; height: 44px; padding: 0 1rem 0 2.6rem; border: 1px solid var(--rule); border-radius: 999px; background: var(--paper); font-family: var(--sans); }
    .plp-facets { display: contents; }
    .plp-sheet-head, .plp-sheet-apply { display: none; }
    .plp-facet { position: relative; }
    .plp-facet-button { list-style: none; cursor: pointer; height: 44px; display: inline-flex; align-items: center; gap: .35rem; padding: 0 1rem; border: 1px solid var(--rule); border-radius: 999px; background: var(--paper); font-family: var(--sans); font-size: .9rem; white-space: nowrap; }
    .plp-facet-button::-webkit-details-marker { display: none; }
    .plp-facet-button::after { content: '▾'; font-size: .7rem; color: var(--muted); }
    .plp-facet[open] > .plp-facet-button, .plp-facet-button:hover { border-color: var(--ink); }
    .plp-facet-n { color: var(--accent); font-weight: 600; }
    .plp-panel { position: absolute; top: calc(100% + .4rem); left: 0; z-index: 30; width: min(320px, 86vw); max-height: 360px; display: flex; flex-direction: column; gap: .5rem; padding: .75rem; border: 1px solid var(--rule); border-radius: 12px; background: var(--paper); box-shadow: 0 18px 40px -18px rgba(14,14,14,.35); }
    .plp-panel-search { height: 38px; padding: 0 .8rem; border: 1px solid var(--rule); border-radius: 8px; background: var(--bg, var(--paper)); font-family: var(--sans); }
    .plp-options { overflow-y: auto; display: flex; flex-direction: column; }
    .plp-option { display: flex; align-items: center; gap: .55rem; padding: .4rem .25rem; border-radius: 6px; font-size: .88rem; cursor: pointer; }
    .plp-option:hover { background: color-mix(in srgb, var(--ink) 5%, transparent); }
    .plp-option[hidden] { display: none; }
    .plp-option-label { flex: 1; }
    .plp-option-count { color: var(--muted); font-size: .8rem; font-variant-numeric: tabular-nums; }
    .plp-panel-empty { margin: .25rem; color: var(--muted); font-size: .85rem; }
    .plp-sort { height: 44px; padding: 0 1rem; border: 1px solid var(--rule); border-radius: 999px; background: var(--paper); font-family: var(--sans); font-size: .9rem; }
    .plp-apply { height: 44px; }
    .js-filters .plp-apply { display: none; }
    .chip { display:inline-flex; align-items:center; gap:.4rem; padding:.35rem .8rem; border:1px solid var(--rule); border-radius:999px; background:var(--paper); font-size:.8rem; color:var(--ink-2); transition:border-color .15s, color .15s; }
    .chip:hover { border-color:var(--ink); color:var(--ink); }
    .chip-clear { color:var(--accent); border-style:dashed; }
    @media (max-width: 720px) {
      .js-filters .plp-facets { display: none; }
      .js-filters .plp-apply { display: none; }
      .js-filters.sheet-open .plp-facets { display: flex; flex-direction: column; gap: .75rem; position: fixed; inset: auto 0 0 0; z-index: 10001; max-height: 82vh; overflow-y: auto; padding: 1rem 16px calc(1rem + env(safe-area-inset-bottom)); background: var(--paper); border-radius: 16px 16px 0 0; box-shadow: 0 -20px 50px -20px rgba(14,14,14,.45); }
      .js-filters.sheet-open .plp-sheet-head { display: flex; justify-content: space-between; align-items: center; }
      .js-filters.sheet-open .plp-sheet-apply { display: block; width: 100%; }
      .js-filters.sheet-open .plp-panel { position: static; width: 100%; max-height: none; box-shadow: none; padding: .5rem 0 0; border: 0; }
      .plp-search { min-width: 0; flex-basis: 100%; max-width: none; }
      .plp-sheet-close { background: none; border: 0; font-size: 1.1rem; cursor: pointer; }
    }
  </style>
  ```

  2. **Eyebrow and heading for a single genre.** In the eyebrow `{% if %}` chain, add `{% elif selected_genre_label %}Genre` after the publisher branch. In the `<h1>` chain, add `{% elif selected_genre_label %}{{ selected_genre_label }}<span class="text-accent">.</span>` after the publisher branch.
  3. **Default lede.** Replace `Independent, modern, hand-curated. Filter by genre or publisher. The shelf rotates every Tuesday.` with `Independent, modern, hand-curated. Filter by genre, topic, author, format or length. The shelf rotates every Tuesday.`
  4. **Chips.**
     - Replace the condition `{% if selected_author or selected_publisher or selected_category or selected_tag or search_query %}` with `{% if filter_chips or selected_publisher or selected_category or selected_tag or search_query %}`.
     - Delete the `{% if selected_author %}…Author: …✕</a>{% endif %}` chip line. In the four remaining chip lines, remove the `{% if selected_author %}author={{ selected_author }}&{% endif %}` fragments.
     - Insert before the `Clear all` link:

     ```django
           {% for c in filter_chips %}<a href="{{ c.href }}" class="chip">{{ c.label }} ✕</a>{% endfor %}
     ```

  5. **The toolbar.** Replace the whole `<form method="get" class="plp-toolbar" …> … </form>` element with `{% include "storefront/_listing_filters.html" %}`.

     This drops:
     - the catalog-category `<select>`, which on dotbooks shows only one category and is replaced by the Genre facet (`?category=` links still work through the hidden field);
     - the author datalist;
     - the old sort `<select>`.

     Keep the `{% if facets %}` attribute-facet panel and its `facet-form` below unchanged.

- [ ] **Step 6: Run the tests to verify they pass, and compile**

Run: `$TEST themes.test_dot_books_listing_filters themes plugins.installed.storefront plugins.installed.book_product`
Expected: OK.

Run: `DATABASE_URL='sqlite:///:memory:' .venv/bin/python -c "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','morph.settings');django.setup();from django.template.loader import get_template as g;[g(t) for t in ('storefront/_listing_filters.html','storefront/product_list.html')];print('compiled')"`
Expected: `compiled`.

Run: `node --check themes/library/dot_books/static/dot_books/listing-filters.js && echo js-ok`
Expected: `js-ok`.

- [ ] **Step 7: Check it in a browser (local)**
  1. Start a local server with dotbooks-like data: `runserver` on the dev database, with `MORPHEUS_ACTIVE_THEME=dot_books`.
  2. Open `/products/` at 1280px and at 390px (Chrome devtools `emulate` viewport `390x844x2,mobile,touch`). Check each of these and fix anything wrong before committing:
     - each panel opens;
     - ticking two genres and closing the panel reloads with both chips;
     - a panel's search narrows the list;
     - Escape closes the panel;
     - on the phone, "Filters (n)" opens the sheet;
     - nothing scrolls sideways.

- [ ] **Step 8: Commit**

```bash
git add themes/library/dot_books/templates/storefront/_listing_filters.html themes/library/dot_books/static/dot_books/listing-filters.js themes/library/dot_books/templates/storefront/product_list.html themes/test_dot_books_listing_filters.py
git commit -m "feat(dot_books): book filters as panels with counts, chips, and a phone sheet

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Docs, release, the whole suite and every gate

**Files:**
- Modify:
  - `CLAUDE.md` (one convention line)
  - `docs/superpowers/specs/2026-10-16-dotbooks-book-filters-design.md` (status)
- Modified by `manage.py release`: `docs/RELEASE_NOTES.md` and `morph/settings.py`

- [ ] **Step 1: Add the CLAUDE.md convention**

After the paragraph that begins `**Convention — a category lists its subtree (v0.100.0).**`, add:

```
**Convention — a listing's extra filters come from the app that owns the data (v0.114.0).** The
storefront's product list fires `LISTING_FACETS` after its own filters; book_product answers with
genre, topic, author, format and length (`book_product/listing_facets.py`: OR inside a facet, AND
across facets, each facet's counts taken with the others applied) and its sorts. The view imports no
book code and a store without the book app shows no book filters. A theme renders `listing_facets`
generically (dot_books: `storefront/_listing_filters.html`). Guarded by
`book_product/tests/test_listing_facets.py` and `storefront/tests/test_listing_facets_seam.py`.
```

- [ ] **Step 2: Mark the spec shipped and cut the release**

Change the spec's status line to `**Status:** shipped in v0.114.0.`

Run:
```bash
DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py release --minor "Better book filters on dotbooks" \
  -m "All books: filter by genre, topic, author, format (print, PDF, audiobook) and length, several values each, with a book count next to every choice." \
  -m "Chosen filters show as removable chips; on a phone the filters open in a sheet; every filtered view is a link you can share." \
  -m "New sorts: Title A–Z, Author A–Z, Shortest, Longest."
DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py release --check
```

Expected: the version is bumped, a dated notes entry is written, and `release --check` passes.

- [ ] **Step 3: Run every gate**

Run:
```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . | tail -1 \
 && DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py check \
 && DATABASE_URL='sqlite:///:memory:' .venv/bin/python manage.py makemigrations --check --dry-run \
 && .venv/bin/python scripts/check_core_boundary.py && .venv/bin/python scripts/check_plugin_boundary.py \
 && .venv/bin/python scripts/check_plugin_standard.py && echo gates-done
```

Expected: all pass, ending with `gates-done`.

- [ ] **Step 4: Run the full suite (in the background)**

Run: `DATABASE_URL='sqlite:///:memory:' REDIS_URL='redis://127.0.0.1:6379/15' MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace,plugins.installed.dsers,plugins.installed.zendrop,plugins.installed.cjdropshipping,plugins.installed.aliexpress' .venv/bin/python manage.py test > /tmp/full-suite.log 2>&1; tail -5 /tmp/full-suite.log`

Expected: `OK`. Every failure is fixed or recorded by name.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-10-16-dotbooks-book-filters-design.md docs/RELEASE_NOTES.md morph/settings.py
git commit -m "chore(release): better book filters on dotbooks

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Deploy and check dotbooks live

**Files:** none. A push to main deploys every store.

- [ ] **Step 1: Push, then wait for every store**

Run: `git push origin main && SMOKE_DEADLINE_SECS=2400 scripts/deploy_smoke.sh $(grep -o "default='v[0-9.]*'" morph/settings.py | grep -o 'v[0-9.]*')`
Expected: `SMOKE OK`.

- [ ] **Step 2: Live checks on dotbooks**
  - **Screenshots:** `https://dotbooks.store/products/?cb=<n>` at 1280px and at 390px (emulated).
  - **A combined filter.** Open `/products/?genre=<slug>&format=print&length=150-300`, then check:
    - the "N books" line equals the number of cards across the pages;
    - the genre panel shows that genre ticked;
    - each chip's ✕ removes only its value.
  - **Canonical:** `/products/?genre=<slug>` still has canonical `https://dotbooks.store/products/` (`curl … | grep canonical`).
  - **Other stores:** Montenegro's `/bookings/`, and Supernatural's and Irving's `/products/` (or `/shop/`), answer 200. Their toolbars are unchanged.
  - **Error log:** no new rows since the deploy (the same in-container query as v0.113.0's check).
  - **CLS:** run a Lighthouse performance audit (chrome devtools) on `/products/`. CLS stays under 0.1.

- [ ] **Step 3: Report**

Report what shipped, the screenshots, and the genre data decisions waiting for the owner:
- the duplicate "Non-fiction";
- "Children" vs "Children's";
- "Mystery" vs "Mystery & Detective";
- curation labels stored as genres.
