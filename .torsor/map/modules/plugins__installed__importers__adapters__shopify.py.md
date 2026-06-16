---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/importers/adapters/shopify.py

Symbols in `plugins/installed/importers/adapters/shopify.py`.

- L28 `_HTTPClient` (class) — Tiny HTTP wrapper. Replaced in tests with a fake.
- L31 `__init__(self, shop: str, token: str, api_version: str='2024-01')` (method)
- L35 `get(self, path: str, params: dict | None=None)` (method)
- L44 `ShopifyImporter` (class)
- L47 `__init__(self, *, shop: str='', token: str='', client: Any | None=None, records: dict[str, Iterable[dict]] | None=None)` (method) — Pass either:
- L72 `iter_products(self)` (method)
- L89 `iter_orders(self)` (method)
- L98 `iter_customers(self)` (method)
- L109 `_run(self)` (method)
- L119 `_import_product(self, record: dict)` (method)
- L184 `_import_customer(self, record: dict)` (method)
- L209 `_import_order(self, record: dict)` (method)
- L238 `_unique_slug(model, seed: str)` (method)
