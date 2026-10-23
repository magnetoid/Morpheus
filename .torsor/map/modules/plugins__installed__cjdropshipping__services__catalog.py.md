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

# plugins/installed/cjdropshipping/services/catalog.py

Symbols in `plugins/installed/cjdropshipping/services/catalog.py`.

- L27 `_price(value)` (function) — A CJ price — a number, a numeric string, or a range like "8.13-8.62" (low end).
- L36 `_images(value)` (function)
- L44 `search(keyword: str, *, page: int=1, size: int=20)` (function)
- L73 `_rate()` (function)
- L81 `product_spec(pid: str)` (function)
- L116 `ship_from()` (function)
- L120 `freight_options(lines: list[dict], country_code: str, zip_code: str='')` (function) — Shipping methods CJ offers for ``lines`` (``[{vid, quantity}]``) to a country, cheapest first.
- L149 `import_cj_product(pid: str)` (function) — Import CJ product ``pid`` as a draft; returns the shared ImportResult.
