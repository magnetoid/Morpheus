# Dotbooks: better book filters on the all-books page

**Status:** shipped in v0.114.0. Owner change during the build: the page has no search box of its own; search lives in the header.
**Owner's request (2026-10-16):** "on dotbooks frontend in all books page, we need more advanced and better
dropdowns filter and more of them."
**Ships as:** one MINOR release.

## What is there today (checked live, 2026-10-16)

`/products/` on dotbooks lists 861 books. It is rendered by `storefront/views/catalog.py:product_list`
and `themes/library/dot_books/templates/storefront/product_list.html`. Its toolbar holds:
- a search box;
- a free-text "Author…" box with a datalist;
- a genre `<select>` fed by catalog categories;
- a sort menu: Newest, Price ↑, Price ↓, Name;
- an Apply button.

Three things are wrong with it:
- **The genre menu never appears.** It lists catalog categories, and only one catalog category has books. The 42 genres in use are `book_product.Genre`.
- **The intro promises "Filter by genre or publisher."** Every book has the same publisher.
- **Each filter takes one value.** The view accepts `?genre=` and `?topic=` as single slugs and filters on `book__genres__slug` directly (a storefront → book_product model path). `?author=` and `?publisher=` go through `book_product.compat`.

**Data on dotbooks' 861 live books.** These numbers decide which filters are worth showing.

| Field | Coverage | Used? |
|---|---|---|
| Genre (`BookProduct.genres`) | 42 genres, 856 books | yes |
| Topic (`BookProduct.topics`) | 1,526 topics: 1,186 cover one book, about 340 cover two or more | yes, topics with 2+ books |
| Author (`BookProduct.author`) | 291 authors, 473 books | yes |
| Format (variant names) | Print 535 · Digital PDF 534 · Audiobook 8 | yes |
| Length (`BookProduct.page_count`) | 501 books: <150 109 · 150–300 168 · 300–500 115 · 500+ 109 | yes |
| Publisher | 2 spellings of DotBooks | no |
| Language | all English | no |
| Publication date | 28 books | no |
| Price | $4.50–$18.99; 806 books cost $7–10 | no; a filter would barely narrow |

## Goal

A shopper narrows 861 books by genre, topic, author, format and length. They can pick several
values in each, they always see how many books each choice leaves, and every state is a URL
they can share.

## Behaviour

**The toolbar.**
- Search stays.
- After it come five filter buttons: Genre, Topic, Author, Format, Length.
- Then a sort menu: Newest, Title A–Z, Author A–Z, Price ↑, Price ↓, Shortest, Longest.
- A button shows its count of chosen values ("Genre · 2").

**A filter panel.** A button opens a panel of checkboxes.
- **Labels:** each choice is labelled with its name and how many books it leaves, given every other active filter.
- **Empty choices:** a choice that would leave zero books is not listed, unless it is already selected.
- **Search box:** Topic and Author panels have a search box that narrows the visible choices as you type. Genre gets one only past 12 choices.

**How filters combine.**
- Choices inside one filter widen the results: Fantasy or Mystery.
- Filters narrow each other: (Fantasy or Mystery) and Print.

**Applying.**
- **With JavaScript:** a change is applied when the panel closes or loses focus, with one page load per panel, not one per checkbox.
- **Without JavaScript:** the panels are `<details>` elements inside the GET form, and the Apply button stays.

**Above the grid.**
- Each chosen value shows as a chip with ✕, followed by "Clear all".
- The result count reads "N books".

**On a phone** (under 720 px):
- The five buttons collapse into one "Filters (n)" button that opens a bottom sheet with each filter as a section.
- The sheet has "Show N books", and nothing scrolls sideways.

**URLs.**
- Filters use repeated keys, as a plain HTML form submits them: `?genre=fantasy&genre=mystery&format=print&length=150-300`.
- The existing single-value links keep working: `?genre=<slug>`, `?topic=<slug>`, `?author=<name>`.
- **Headings.** When exactly one author or one genre is chosen and nothing else, the page heading and lede stay the dedicated ones ("Books by Agatha Christie"); the templates already do this for author and publisher.
- **Copy.** The intro stops promising a publisher filter. It reads: "Independent, modern, hand-curated. Filter by genre, topic, author, format or length. The shelf rotates every Tuesday."

**Format values.**
- Print, Digital PDF and Audiobook are matched on variant names (`ProductVariant.name`, case-insensitive).
- A book with no variants counts as Print (on dotbooks none of the 324 simple products has a digital file).

**Length values.**
- The buckets are `under-150`, `150-300`, `300-500` and `500-plus`, on `page_count`.
- Books with no page count appear only when no length is chosen.

**Search engines.**
- No change is needed. On dotbooks a filter parameter is consolidated by the store's index rules (`seo/rules/params.py`: unlisted parameters consolidate), so a filtered URL is canonical to `/products/` (verified live 2026-10-16 for `?genre=` and `?author=`).
- The indexable pages for a genre, topic or author remain `/genres/<slug>/`, `/topics/<slug>/` and `/authors/<slug>/`.
- Rules are not seeded by code (`RECOMMENDED_RULES` is opt-in by design), so this release adds none.

## Design

**One seam: the book app supplies the facets.** A new filter, `MorpheusEvents.LISTING_FACETS`, has:
- **value:** `{'queryset': QuerySet[Product], 'facets': list[dict]}`;
- **kwargs:** `params` (the request's `QueryDict`) and `surface` (`'product_list'`).

The storefront view fires it after its own filters (search, category, collection, tag, price,
attribute facets) and before sorting and pagination. It renders whatever comes back as
`listing_facets` and uses the returned queryset.

**`book_product` answers it** (`book_product/listing_facets.py`). For each of its five facets it:
1. reads that facet's selected values from `params`;
2. narrows the queryset by all five facets (each an OR within the facet);
3. computes each facet's options with counts against the queryset narrowed by the OTHER four facets only. That is five aggregate queries, at most a few hundred rows each on 861 books.

Each facet comes back as a dict:

```python
{
    'key': 'genre',
    'label': 'Genre',
    'searchable': False,
    'options': [{'value': 'fantasy', 'label': 'Fantasy', 'count': 35, 'selected': True}],
}
```

The order is Genre, Topic, Author, Format, Length.
- **Topic** lists options with a count of 2 or more, plus any selected ones, sorted by count.
- **Author** is sorted by name.
- **Genre** is sorted by count.

**The storefront view drops its own book paths.** That means:
- the `book__genres__slug` and `book__topics__slug` filters;
- the `compat.product_ids_for` author filter;
- the `distinct_values('author')` datalist.

The book app now owns those parameters. The `publisher` parameter keeps its existing compat path, so its old links still work; there is no publisher control.

A store without the book app gets no facets and its toolbar is unchanged: Montenegro, Supernatural and Irving use their own themes' templates, which ignore `listing_facets`.

**Sort.** The view's sort map gains:
- `title` (`name`);
- `author`, which annotates `book__author`;
- `shortest` and `longest`, on `book__page_count`, nulls last.

Sorts that need book fields are only offered when the book app is active. The view asks the book app for them through the same filter: `value['sorts']`, a list of `(key, label, order_by)`.

**The theme's component.**
- `dot_books/templates/storefront/_listing_filters.html` renders the toolbar from `listing_facets`.
- `dot_books/static/dot_books/listing-filters.js` (about 150 lines, no dependencies) adds:
  - panels that open on click and close on Escape or outside click;
  - the type-to-narrow search;
  - apply-on-close;
  - the phone sheet.
- The panels are keyboard accessible: buttons with `aria-expanded`, labels on checkboxes, focus returned on close.
- Styles go in the page's `extra_head` block, before the markup. A `<style>` after the grid is the CLS landmine in CLAUDE.md.

**Genre data flagged, not hidden.** The genre list shows these problems:
- two separate "Non-fiction" genres (296 and 280 books);
- near-duplicates such as "Children" and "Children's", and "Mystery" and "Mystery & Detective";
- curation lists stored as genres ("Independent presses we love", "Editor's pick…").

This release shows every active genre as stored. Merging or renaming them is content work for the owner. It is listed for decision, not done here.

## Testing

**`book_product/tests/test_listing_facets.py`:**
- options and counts per facet;
- OR within a facet and AND across facets;
- counts that ignore the facet's own selection;
- a choice that would leave zero books is hidden unless selected;
- topics with one book are omitted;
- the length buckets, including books with no page count;
- format matching on variant names;
- the old single-value `?genre=`, `?topic=` and `?author=` URLs.

**`storefront/tests/test_listing_facets_seam.py`:**
- with the book app off, there are no facets and the old parameters are ignored without error;
- the view uses the returned queryset;
- pagination keeps the repeated keys.

**`themes` tests:**
- `_listing_filters.html` compiles and renders every facet and chip;
- the no-JavaScript form submits repeated keys;
- the intro copy no longer mentions publisher.

**Whole-change checks:** the full suite plus every CI gate.

**Live, after deploy, on dotbooks:**
- desktop and 390 px screenshots;
- a genre + format + length combination whose count matches the grid;
- chips and Clear all work;
- `/products/?genre=<slug>` still canonical to `/products/`;
- Lighthouse CLS unchanged on `/products/`.
