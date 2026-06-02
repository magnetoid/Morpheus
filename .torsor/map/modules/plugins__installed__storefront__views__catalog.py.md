---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:53'
updated: '2026-06-02T18:07:53'
---

# plugins/installed/storefront/views/catalog.py

Symbols in `plugins/installed/storefront/views/catalog.py`.

- L29 `product_list(request)` (function) — Product list with merchant-friendly facets: category, tag, price range,
- L259 `_apply_search(qs, q: str)` (function) — Three-tier retrieval:
- L307 `_metafield_search_ids(q: str)` (function) — Return product IDs whose book.author/publisher/isbn metafield contains q.
- L327 `product_detail(request, slug)` (function)
- L514 `_pdp_faqs(slug: str, *, product_row=None)` (function) — Return ``[{q, a}, ...]`` from the seo.pdp_faqs metafield, or [].
- L556 `_published_reviews(slug: str, limit: int=4, *, product_row=None)` (function) — Return ``[{stars, body, author_name, created_at}, ...]`` for the PDP.
- L601 `_book_specs(slug: str)` (function) — Return ``[{label, value, link?}, ...]`` of book metafields for the PDP.
- L632 `_related_products(current_slug: str, limit: int=4)` (function) — AI-driven 'you might also like' for the PDP.
- L668 `search(request)` (function)
- L761 `category_detail(request, slug)` (function) — Category landing — products + editorial framing.
- L821 `collection_detail(request, slug)` (function) — Collection landing page — clean SEO URL /collection/<slug>/ for a
- L872 `author_detail(request, slug)` (function) — Author landing page — bibliography + optional bio.
- L961 `staff_picks(request)` (function) — Curated staff picks — Collection-backed.
- L1013 `categories(request)` (function)
- L1054 `quick_search(request)` (function) — Lightweight JSON endpoint for the topbar quick-results dropdown.
