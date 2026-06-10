---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/catalog/services/_helpers.py

Symbols in `plugins/installed/catalog/services/_helpers.py`.

- L80 `PublishError` (class) — Raised when a digital-product publish call can't proceed.
- L85 `_is_safe_remote_host(host: str)` (function) — Return True iff `host` resolves only to public, routable addresses.
- L132 `_is_public_ip(ip: ipaddress._BaseAddress)` (function)
- L145 `_validate_https_url(url: str, *, field: str)` (function)
- L153 `_download(url: str, *, max_bytes: int, field: str)` (function) — Stream `url` → (body, content_type, filename). Hard size + timeout caps.
- L187 `_unique_slug(base: str)` (function) — Return a slug that doesn't collide with an existing product.
- L202 `_unique_sku(suggested: str, *, fallback_base: str)` (function)
- L218 `_coerce_price(amount: Any)` (function)
- L231 `_serialize_product(p)` (function)
- L245 `_serialize_category(c)` (function)
- L254 `_serialize_image(img)` (function)
- L265 `_serialize_variant(v)` (function)
- L289 `_apply_variant_fields(variant, fields: dict, *, allow_sku_collision_check: bool=True)` (function) — Mutate `variant` in place with whatever fields are present. Skips
