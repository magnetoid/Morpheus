---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/storefront/views/catalog.py

Symbols in `plugins/installed/storefront/views/catalog.py`.

- L29 `product_list(request)` (function) — Product list with merchant-friendly facets: category, tag, price range,
- L243 `_apply_search(qs, q: str)` (function) — Three-tier retrieval:
- L291 `_metafield_search_ids(q: str)` (function) — Return product IDs whose book.author/publisher/isbn metafield contains q.
- L311 `product_detail(request, slug)` (function)
- L499 `_pdp_faqs(slug: str, *, product_row=None)` (function) — Return ``[{q, a}, ...]`` from the seo.pdp_faqs metafield, or [].
- L541 `_published_reviews(slug: str, limit: int=4, *, product_row=None)` (function) — Return ``[{stars, body, author_name, created_at}, ...]`` for the PDP.
- L585 `_product_codes(product_row)` (function) — Product identifier codes (ISBN/EAN/GTIN/UPC/MPN/ASIN) for the PDP.
- L595 `_book_specs(slug: str)` (function) — Book attributes for the PDP ``[{label, value, link?}, ...]``.
- L612 `_book_specs_from_model(slug, slugify, urlencode)` (function)
- L653 `_book_specs_from_metafields(slug, slugify, urlencode)` (function)
- L678 `_related_products(current_slug: str, limit: int=4)` (function) — AI-driven 'you might also like' for the PDP.
- L714 `search(request)` (function)
- L807 `_attach_book_authors(products)` (function) — Attach ``.author_name`` to each product for the card grid (no N+1).
- L846 `category_detail(request, slug)` (function) — Category landing — products + editorial framing.
- L930 `collection_detail(request, slug)` (function) — Collection landing page — clean SEO URL /collection/<slug>/ for a
- L1004 `author_detail(request, slug)` (function) — Author landing page — bibliography + optional bio.
- L1094 `staff_picks(request)` (function) — Curated staff picks — Collection-backed.
- L1146 `categories(request)` (function)
- L1187 `quick_search(request)` (function) — Lightweight JSON endpoint for the topbar quick-results dropdown.
