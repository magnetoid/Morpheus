# Genres & Topics for books — 2026-06

> **Status: BUILT on branch `feat/book-genres-topics` (not yet deployed).**
> Phases 1–3 + admin CRUD shipped: Genre/Topic models + M2M, schema migration
> 0005, the destructive data migration 0006 (categories→genres, Books root,
> delete old), genre/topic index+detail pages, nav rewired to genres+topics,
> `/category/…`→`/genre/…` 301s, book-form assignment, PDP breadcrumb/eyebrow.
> 55 book_product tests + storefront suite green on sqlite. **Not pushed** — the
> data migration is **destructive on prod** (deletes category rows); deploy
> deliberately (back up the DB; CI Postgres `migrations` job is the real gate).
> **Deferred (Phase 4 polish):** sitemap genre/topic entries + drop dead
> `/category/` URLs; `?category=`→`?genre=` PLP/search facet; `_CATEGORY_INTROS`
> → genre `description`; seed `Books`+genres+sample topics; a first-class
> dashboard Genre/Topic editor (admin CRUD covers it for now).

**Goal (user):** books are organised by **Genre** (Fiction, Poetry, Essays, …)
and **Topic** (subject tags: WWII, grief, space exploration). Today those
"genres" are abused as catalog **Categories**; conceptually there should be
**one** category — **Books** — and genre/topic become first-class book
taxonomies. Migrate the existing genre-categories → Genres, add Topics, and
replace the storefront's category links with Genre + Topic links.

## Decisions (locked)
- **Genres: flat list** (no sub-genre hierarchy) — mirrors today's flat
  categories exactly. Topics: flat subject tags.
- **Old genre-categories: deleted** after products are reassigned to the single
  `Books` category. End state: `Books` is the only catalog `Category`.
- **Plan first, build later.**

## What exists today
- **Category** = `catalog/models.py:44` — an MPTT tree; `Product.category` FK +
  `additional_categories` M2M (`:216`, `:222`). Seed defines 6 flat top-level
  categories (`demo_data/seeds.py:34`: fiction, nonfiction, poetry, essays,
  children, art-design) — **these are the genres.** No `Books` root exists.
- **No genre/topic field** anywhere except as these categories. `BookProduct`
  (`book_product/models.py:38`, OneToOne→`catalog.Product`) has author/publisher/
  series/imprint/etc. but **no subject/genre/BISAC**.
- **Proven taxonomy pattern** in `book_product` (authors/publishers/series/
  imprints): `urls.py` routes `/<taxonomy>/` (index) + `/<taxonomy>/<slug>/`
  (detail); `views.py` `_taxonomy_root` / `_slug_facet` / `_render`;
  `BookTaxonomyRoot` (root-page SEO) + `BookTaxonomyTerm` (per-term SEO overlay).
  **Genre/Topic follow this pattern** — but as *curated models*, not
  auto-discovered string fields.
- **Storefront category links live in 3 layers** (all must be rewired):
  - context: `catalog/context_processors.py:14` `nav_categories()`
  - templates: `themes/library/dot_books/templates/storefront/_nav_mega_genres.html`,
    `base.html:708-712` (mobile nav), `category_detail.html`
  - views: `storefront/views/catalog.py:855` `category_detail`, `:29`
    `product_list`, `:784` `_CATEGORY_INTROS` (hard-coded per-slug intros).

## Model design (book_product owns it)

Genre/Topic are **book concepts** → they live in `book_product`, not catalog
(architectural compass: catalog owns the generic Category kernel; book-specific
taxonomy is the plugin's). Curated rows (merchant-managed), so dedicated models
with their **own SEO fields** — no `BookTaxonomyTerm` overlay needed.

```
Genre   (book_product)
  id(uuid) · name · slug(unique) · description
  meta_title · meta_description · image · sort_order · is_active
Topic   (book_product)   # identical shape; semantic difference only
  id(uuid) · name · slug(unique) · description
  meta_title · meta_description · image · sort_order · is_active

BookProduct.genres = M2M(Genre, blank=True, related_name='books')
BookProduct.topics = M2M(Topic, blank=True, related_name='books')
```

A book has **many** genres and **many** topics (multi-value — that's why M2M,
not the single-CharField auto-discovery used for author/publisher).

## Phases (each independently shippable; one merge at a time)

### Phase 1 — models + dashboard editors *(no storefront change, invisible)*
- Add `Genre` + `Topic` models + the two M2M fields on `BookProduct`. Migration
  adds tables + through-tables only (no data move yet).
- `book_product` dashboard pages: **Genres** and **Topics** CRUD (name, slug,
  description, image, SEO, sort, active) via `contribute_dashboard_pages()`;
  owner-gated. Add genre/topic multi-select to the **book product form**.
- **Verify:** create a genre, tag a book, see it on the book in the dashboard;
  permission-boundary tests; `makemigrations --check` clean.

### Phase 2 — data migration *(destructive on prod — run deliberately)*
A single data migration (idempotent where possible):
1. **Create the `Books` root category** (`get_or_create` slug=`books`).
2. **For each existing top-level Category** (the genres): `get_or_create` a
   `Genre` carrying its name/slug/description/meta/image/sort_order.
3. **For each book Product**, union its `category` + `additional_categories`,
   map each to the matching `Genre`, and add to `product.book.genres`. Then set
   `product.category = Books` and clear `additional_categories`.
4. **Guard for non-book products:** only reassign products that have a
   `BookProduct`. If any non-book product still references an old category, **do
   not delete that category** (log it). (Assumption: single-vertical bookstore —
   expected count is 0, but the guard prevents orphaning a non-book product.)
5. **Delete** the now-unreferenced old genre-categories. `Books` remains.
- Topics get **no data** (none exist) — start empty; merchant curates in Phase 1
  editor.
- **Landmine:** `Product.category` is likely non-null — Step 3 must set `Books`
  *before* Step 5 deletes, or the FK breaks. **FK-type:** all these are
  uuid→uuid, plain reassignment, no `AlterField` cross-type retarget.
- **Verify on a DB copy first:** every book ends with `category=Books` + ≥1
  genre; genre counts match the old category product counts; no category row
  except `Books` survives; non-book guard leaves nothing orphaned. CI Postgres
  `migrations` job must pass (don't trust sqlite for the delete/reassign).

### Phase 3 — storefront rewire (genre/topic nav + pages + redirects)
- **Index + detail pages** following the existing taxonomy pattern:
  `/genres/` + `/genre/<slug>/`, `/topics/` + `/topic/<slug>/`, registered via
  `book_product` `register_urls`, reusing `taxonomy_root.html` / `book_facet.html`
  (genre/topic detail queries `BookProduct.objects.filter(genres=…)`).
- **Nav:** `book_product` provides a `nav_genres` / `nav_topics` context
  processor (mirrors `nav_categories`, cached). Update the theme's
  `_nav_mega_genres.html` + `base.html:708` to render genres (+ a topics column)
  instead of categories. *(Disable book_product → genre nav vanishes; `Books`
  category remains — disable-safe.)*
- **301 redirects (SEO-critical):** old `/category/<slug>/` URLs are indexed.
  Add permanent redirects `/category/<genre-slug>/ → /genre/<genre-slug>/` (and
  `/categories/ → /genres/`) so link equity + bookmarks survive. This is the
  reason to keep the slugs identical in Phase 2.
- **Verify:** genre/topic index + detail render with correct products; old
  category URL 301s to the genre URL; mega-menu + mobile nav show genres/topics;
  breadcrumbs read Genre, not Category.

### Phase 4 — cleanup
- Replace `_CATEGORY_INTROS` (`catalog.py:784`) with the genre's own
  `description` (DB-driven, not hard-coded per slug).
- Sitemap: emit `/genre/<slug>/` + `/topic/<slug>/` (ADR 0008: every page in the
  sitemap); drop the dead `/category/<slug>/` entries (now redirects).
- Search facets / any PLP `?category=` filter → `?genre=` (keep `category=Books`
  working or drop it as redundant).
- Update `demo_data/seeds.py` so fresh installs seed `Books` + genres + a few
  topics, not the old flat categories.
- **Verify:** sitemap lists genre/topic pages; search facets by genre; fresh
  `seed` produces the new structure; full storefront smoke.

## Deliberately deferred
- **Hierarchical genres** (sub-genres). Flat now; a `parent` FK can come later
  without a data move. **Flat is the deliberate SEO choice**, not a shortcut:
  sub-genres tend to produce thin, near-duplicate pages (crawl-budget waste,
  poor indexing) and bury pages deeper than ~2 clicks. The Genre × Topic
  two-axis design already captures the long-tail (Fiction × "WWII") via flat,
  content-rich, shallow pages — the modern faceted approach. Add a `parent` FK
  only for a sub-genre with real search volume *and* enough books to avoid a
  thin page.
- **BISAC / external subject codes** mapping. Topics are free curated tags for
  now.
- **Auto-tagging books to genres/topics by AI.** A later Linda tool; manual
  curation first.

## Landmines
- **Destructive prod migration.** Phase 2 deletes category rows — **back up the
  prod DB first**, dry-run on a copy, and run it as its own deploy (not batched).
- **SEO regression if redirects are skipped.** Indexed `/category/<slug>/` URLs
  must 301 to `/genre/<slug>/`; keeping slugs identical (Phase 2) is what makes
  the redirect 1:1.
- **Non-book products.** The category collapse is only valid because every
  product is a book; the Phase 2 guard (Step 4) is mandatory, not optional —
  it's what makes "delete all but Books" safe.
- **`Product.category` non-null.** Reassign to `Books` before deleting old rows.
- **Disable-test.** Genre/Topic models + nav are `book_product`-owned; disabling
  it removes the genre nav and pages, leaving the `Books` category (core catalog)
  intact.
- **sqlite vs Postgres.** The reassign+delete migration must be validated by CI's
  Postgres `migrations` job; a green sqlite run is not sufficient.

## Verification per phase
`ruff check . && ruff format --check .`, `python manage.py check`,
`makemigrations --check --dry-run`,
`DATABASE_URL='sqlite:///:memory:' python manage.py test plugins.installed.book_product plugins.installed.catalog plugins.installed.storefront`;
CI Postgres `migrations` job for Phase 2; smoke genre/topic pages + an old
category-URL 301 against the live deploy.
