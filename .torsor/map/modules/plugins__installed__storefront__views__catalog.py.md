---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/storefront/views/catalog.py

Symbols in `plugins/installed/storefront/views/catalog.py`.

- L33 `_paginate(qs, per_page, request)` (function) — Page a listing, and 404 a page number that isn't there.
- L53 `_surface_reorder(request, surface, products)` (function) — Merchandising takeover (STOREFRONT_PRODUCTS, reorder-only, fail-soft).
- L76 `product_list(request)` (function) — Product list with merchant-friendly facets: category, tag, price range,
- L455 `_apply_search(qs, q: str)` (function) — Three-tier retrieval:
- L508 `_metafield_search_ids(q: str)` (function) — Return product IDs whose book.author/publisher/isbn metafield contains q.
- L530 `product_detail(request, slug)` (function)
- L751 `_pdp_faqs(slug: str, *, product_row=None)` (function) — Return ``[{q, a}, ...]`` from the seo.pdp_faqs metafield, or [].
- L793 `_published_reviews(slug: str, limit: int=4, *, product_row=None)` (function) — Return ``[{stars, body, author_name, created_at}, ...]`` for the PDP.
- L837 `_product_codes(product_row)` (function) — Product identifier codes (ISBN/EAN/GTIN/UPC/MPN/ASIN) for the PDP.
- L849 `_product_seo_extra(product_row, primary_image, hero_image, review_summary, reviews)` (function) — SAFE-assembled Product JSON-LD enrichments (image / aggregateRating /
- L885 `_video_seo_data(videos, product)` (function) — Plain dicts for VideoObject JSON-LD from ProductVideo rows. Needs a
- L908 `_book_jsonld_data(product_row, product, product_codes, out_of_stock)` (function) — Assemble the plain dict for ``{% seo_book_jsonld %}`` from SAFE sources.
- L955 `_book_specs(slug: str)` (function) — Book attributes for the PDP ``[{label, value, link?}, ...]``.
- L972 `_book_specs_from_model(slug, slugify, urlencode)` (function)
- L1016 `_book_specs_from_metafields(slug, slugify, urlencode)` (function)
- L1043 `_related_products(current_slug: str, limit: int=4, *, request=None)` (function) — 'You might also like' for the PDP — candidates contributed by
- L1088 `language_prefix(request)` (function) — `/sr` while serving the Serbian tree — see `core.utils.i18n`.
- L1095 `search_results_path(request)` (function) — Where a keyword search lands, in the visitor's language.
- L1112 `search(request)` (function)
- L1228 `_attach_book_authors(products)` (function) — Attach ``.author_name`` to each product for the card grid (no N+1).
- L1268 `_listing_description(name: str, products, limit: int=155)` (function) — `<name>: <first products>.` — for a listing nobody described.
- L1282 `category_detail(request, slug)` (function) — Category landing — products + editorial framing.
- L1406 `collection_detail(request, slug)` (function) — Collection landing page — clean SEO URL /collection/<slug>/ for a
- L1501 `author_detail(request, slug)` (function) — Author landing page — bibliography + optional bio.
- L1603 `staff_picks(request)` (function) — Curated staff picks — Collection-backed.
- L1657 `categories(request)` (function) — The catalogue's category index.
- L1733 `quick_search(request)` (function) — Lightweight JSON endpoint for the topbar quick-results dropdown.
