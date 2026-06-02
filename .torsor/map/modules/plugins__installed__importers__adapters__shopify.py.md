---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/importers/adapters/shopify.py

Symbols in `plugins/installed/importers/adapters/shopify.py`.

- L26 `_HTTPClient` (class) — Tiny HTTP wrapper. Replaced in tests with a fake.
- L29 `__init__(self, shop: str, token: str, api_version: str='2024-01')` (method)
- L33 `get(self, path: str, params: dict | None=None)` (method)
- L41 `ShopifyImporter` (class)
- L44 `__init__(self, *, shop: str='', token: str='', client: Any | None=None, records: dict[str, Iterable[dict]] | None=None)` (method) — Pass either:
- L69 `iter_products(self)` (method)
- L86 `iter_orders(self)` (method)
- L95 `iter_customers(self)` (method)
- L106 `_run(self)` (method)
- L116 `_import_product(self, record: dict)` (method)
- L179 `_import_customer(self, record: dict)` (method)
- L204 `_import_order(self, record: dict)` (method)
- L233 `_unique_slug(model, seed: str)` (method)
