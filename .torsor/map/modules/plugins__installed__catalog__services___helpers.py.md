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

# plugins/installed/catalog/services/_helpers.py

Symbols in `plugins/installed/catalog/services/_helpers.py`.

- L78 `PublishError` (class) — Raised when a digital-product publish call can't proceed.
- L83 `_is_safe_remote_host(host: str)` (function) — Delegates to the core egress gate. This check used to live here in full;
- L96 `_validate_https_url(url: str, *, field: str)` (function)
- L104 `_download(url: str, *, max_bytes: int, field: str)` (function) — Stream `url` → (body, content_type, filename). Hard size + timeout caps.
- L138 `_unique_slug(base: str)` (function) — Return a slug that doesn't collide with an existing product.
- L153 `_unique_sku(suggested: str, *, fallback_base: str)` (function)
- L169 `_coerce_price(amount: Any)` (function)
- L182 `_serialize_product(p)` (function)
- L196 `_serialize_category(c)` (function)
- L205 `_serialize_image(img)` (function)
- L216 `_serialize_variant(v)` (function)
- L240 `_variant_currency(variant)` (function) — The currency a variant's amounts default to: its own price's, else its
- L252 `_apply_variant_fields(variant, fields: dict, *, allow_sku_collision_check: bool=True)` (function) — Mutate `variant` in place with whatever fields are present. Skips
