# Retire `book.*` metafields → BookProduct model

> Book attributes (author, publisher, pages, synopsis, …) now live on the
> `BookProduct` model (book_product plugin). `book.*` metafields are legacy.
> This migrates every reader to the model and removes the metafield dependency.
> Bigger than it looks — `book.*` is read in ~10 files across catalog, SEO,
> search, and webstories.

## Strategy
A shared **model-first, metafield-fallback** helper (`book_product/compat.py`:
`distinct_values`, `product_ids_for`, `resolve_slug`) bridges the transition:
the model is authoritative; legacy metafields (seed data, Gutenberg imports,
un-backfilled rows) still resolve until writers + remaining readers move. Once
done, drop the fallback and the metafields. Data is moved by the 0002 data
migration + the `backfill_book_product` command.

## Reader/writer surface map (from grep)
- **catalog browse** (storefront/catalog.py): PLP `?author=`/`?publisher=` filter,
  `available_authors` facet, `author_detail`, `_attach_book_authors`. ✅ DONE
- **nav** (catalog/context_processors.py): `nav_authors`. ✅ DONE
- **PDP** (storefront/catalog.py `_book_specs`): already model-first (P6b). ✅
- **SEO** (seo/...): `templatetags/seo.py` book specs; `services/jsonld.py` Book
  schema.org; `services/sitemaps.py` author sitemap; `services/ai_feeds.py`;
  `services/audit.py`. ✅ DONE — all route through `compat.book_attrs` /
  `distinct_values`; jsonld Book schema verified from a model-only product.
- **search** (catalog/search/django_backend.py, typesense_backend.py): index
  book.author/publisher/isbn. ⬜ TODO — affects search relevance/index.
- **webstories** (webstories/services.py): synopsis/author panel. ⬜ TODO
- **writers**: demo_data/seeds+services, digital_products convert_gutenberg —
  still WRITE `book.*`. ⬜ TODO — point at BookProduct (or rely on backfill).
- **identifiers** (metafields/identifiers.py:43): legacy ISBN read — separate
  concern (ISBN stays in the `identifiers` namespace; leave).

## Phases
1. **Catalog browse + nav → model-first/fallback.** ✅ DONE (compat helper; 7 tests).
2. **SEO surfaces → model-first/fallback** (jsonld, sitemaps, ai_feeds, audit,
   templatetags). Route through compat / read BookProduct. Verify structured
   data + sitemaps unchanged for existing books. ⬜
3. **Search backends → model.** Index from BookProduct; reindex. ⬜
4. **webstories → model.** ⬜
5. **Writers → model.** demo_data + convert_gutenberg write BookProduct (or run
   backfill post-import). ⬜
6. **Drop the fallback + delete metafields.** Once 2–5 done and a backfill has
   run in prod: remove the metafield branches from compat, optionally a data
   migration to delete `namespace='book'` rows (keep `identifiers`). ⬜

## Landmines
- SEO structured-data / sitemaps are the blast radius — migrate carefully + diff
  output for existing books before/after.
- Keep ISBN/EAN/GTIN in the `identifiers` namespace (not `book`) — untouched.
- Every compat read is fail-soft; new books (model-only) must appear everywhere
  once a surface is migrated (today SEO/search still read metafields, so new
  model-only books are invisible there until phase 2–4 — known gap).

## Status log
- 2026-06: Phase 1 shipped — catalog browse (PLP filter, facet, author_detail,
  author-name annotation) + nav_authors read model-first via book_product.compat;
  metafield fallback preserved. 7 tests (compat union + nav regression).
- 2026-06: Phase 2 shipped — all SEO surfaces route through compat: jsonld Book
  schema.org, the AI markdown feed, the SEO audit's author/E-E-A-T check, the
  PDP spec template tag (`book_facts_jsonld`), and the author sitemap
  (`distinct_values`). Added `compat.book_attrs(product)` — a drop-in `{key:value}`
  dict, model-first + book.* fallback. Verified Book schema emits from a
  model-only product (5 compat tests incl. a jsonld assertion).
- **Remaining:** search backends (3), webstories (4), writers (5),
  drop-fallback + delete metafields (6). Search is the next blast-radius item.
