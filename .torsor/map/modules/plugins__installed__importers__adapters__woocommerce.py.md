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

# plugins/installed/importers/adapters/woocommerce.py

Symbols in `plugins/installed/importers/adapters/woocommerce.py`.

- L24 `_HTTPClient` (class)
- L25 `__init__(self, *, base_url: str, consumer_key: str, consumer_secret: str)` (method)
- L29 `get(self, path: str, params: dict | None=None)` (method)
- L48 `WooImporter` (class)
- L51 `__init__(self, *, base_url: str='', consumer_key: str='', consumer_secret: str='', client: Any | None=None, records: dict[str, Iterable[dict]] | None=None)` (method)
- L73 `iter_products(self)` (method)
- L89 `iter_customers(self)` (method)
- L97 `iter_orders(self)` (method)
- L105 `_run(self)` (method)
- L115 `_import_product(self, record: dict)` (method)
- L149 `_import_customer(self, record: dict)` (method)
- L167 `_import_order(self, record: dict)` (method)
- L189 `_unique_slug(seed: str)` (method)
