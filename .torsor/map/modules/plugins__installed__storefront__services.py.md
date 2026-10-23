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

# plugins/installed/storefront/services.py

Symbols in `plugins/installed/storefront/services.py`.

- L6 `page_intro(request, page: str)` (function) — Merchant-edited intro copy + meta for a built-in listing page.
- L36 `store_name()` (function) — The merchant's own store name — never a hardcoded brand.
- L55 `store_blurb()` (function) — The merchant's own store description, or '' when they haven't written one.
- L71 `catalogue_label()` (function) — What this store calls "everything it sells", for titles + breadcrumbs.
- L87 `staff_picks_collection()` (function) — The collection behind /staff-picks/ — `staff-picks`, else the legacy slug.
- L97 `stocked_category_ids()` (function) — Pks of active categories that list at least one active product.
- L119 `journal_has_entries()` (function) — Whether /journal/ would list at least one live post.
- L133 `vendor_nouns()` (function) — `(singular, plural)` — what this store calls its vendors, in the visitor's language.
