---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/booking_marketplace/products.py

Symbols in `plugins/installed/booking_marketplace/products.py`.

- L22 `has_markup(text: str)` (function) — Whether the text is the product editor's rich text rather than plain text.
- L27 `plain_text(text: str)` (function) — The Product's rich text as the listing's plain-text copy.
- L44 `_clip(text: str, limit: int)` (function) — The text cut at a word to fit `limit` characters, with an ellipsis.
- L51 `_same_text(a: str, b: str)` (function) — Equal but for whitespace. A browser posts a textarea's line breaks as CRLF and drops
- L57 `_listing_copy(service, field: str, value: str)` (function) — What the listing keeps of a Product text field: plain, and short enough for its column.
- L68 `_resolve_slug(service)` (function) — The Product to reuse, and the slug to use.
- L92 `_stored(fieldfile)` (function)
- L99 `_copy_images(service, product)` (function) — The listing photo (primary) then its gallery, for a product with no photos yet.
- L128 `ensure_product(service)` (function) — Link the listing to its Product, creating it from the listing if needed.
- L164 `_point_product_url(product, service)` (function) — An experience is a page at /bookings/<slug>/; its product URL leads there.
- L189 `sync_from_product(product)` (function) — Copy the Product's shared fields onto its listing.
- L220 `sync_to_product(service)` (function) — Copy a host's or the listing editor's edits of the shared fields onto the Product.
- L249 `save_listing(service)` (function) — After a listing is saved by its host or the editor: link its Product, push the edits.
- L255 `on_product_updated(*, product=None, **_)` (function) — PRODUCT_UPDATED: the product editor (or Linda) changed a listing's product.
