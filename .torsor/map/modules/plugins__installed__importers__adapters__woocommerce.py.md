---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/importers/adapters/woocommerce.py

Symbols in `plugins/installed/importers/adapters/woocommerce.py`.

- L24 `_HTTPClient` (class)
- L25 `__init__(self, *, base_url: str, consumer_key: str, consumer_secret: str)` (method)
- L29 `get(self, path: str, params: dict | None=None)` (method)
- L38 `WooImporter` (class)
- L41 `__init__(self, *, base_url: str='', consumer_key: str='', consumer_secret: str='', client: Any | None=None, records: dict[str, Iterable[dict]] | None=None)` (method)
- L63 `iter_products(self)` (method)
- L79 `iter_customers(self)` (method)
- L87 `iter_orders(self)` (method)
- L95 `_run(self)` (method)
- L105 `_import_product(self, record: dict)` (method)
- L139 `_import_customer(self, record: dict)` (method)
- L157 `_import_order(self, record: dict)` (method)
- L179 `_unique_slug(seed: str)` (method)
