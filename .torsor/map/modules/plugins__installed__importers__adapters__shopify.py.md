---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/importers/adapters/shopify.py

Symbols in `plugins/installed/importers/adapters/shopify.py`.

- L28 `_HTTPClient` (class) — Tiny HTTP wrapper. Replaced in tests with a fake.
- L31 `__init__(self, shop: str, token: str, api_version: str='2024-01')` (method)
- L35 `get(self, path: str, params: dict | None=None)` (method)
- L46 `ShopifyImporter` (class)
- L49 `__init__(self, *, shop: str='', token: str='', client: Any | None=None, records: dict[str, Iterable[dict]] | None=None)` (method) — Pass either:
- L74 `iter_products(self)` (method)
- L91 `iter_orders(self)` (method)
- L100 `iter_customers(self)` (method)
- L111 `_run(self)` (method)
- L121 `_import_product(self, record: dict)` (method)
- L186 `_import_customer(self, record: dict)` (method)
- L211 `_import_order(self, record: dict)` (method)
- L240 `_unique_slug(model, seed: str)` (method)
