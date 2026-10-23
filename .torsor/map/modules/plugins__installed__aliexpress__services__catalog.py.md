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

# plugins/installed/aliexpress/services/catalog.py

Symbols in `plugins/installed/aliexpress/services/catalog.py`.

- L32 `_price(value)` (function)
- L40 `ship_to()` (function)
- L44 `ae_country(code: str)` (function) — AliExpress calls the United Kingdom "UK"; every other ISO code passes through.
- L50 `search(keyword: str, *, page: int=1, size: int=20)` (function)
- L85 `_sku_name(sku: dict)` (function)
- L94 `_sku_image(sku: dict)` (function)
- L101 `product_detail(product_id: str)` (function)
- L122 `product_spec(product_id: str)` (function)
- L156 `_int(value)` (function)
- L163 `freight_options(product_id: str, sku_id: str, quantity: int, country_code: str)` (function)
- L194 `import_ae_product(product_id: str)` (function) — Import AliExpress product ``product_id`` as a draft; returns the shared ImportResult.
