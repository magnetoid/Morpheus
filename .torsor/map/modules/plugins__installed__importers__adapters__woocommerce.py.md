---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/importers/adapters/woocommerce.py

Symbols in `plugins/installed/importers/adapters/woocommerce.py`.

- L22 `_HTTPClient` (class)
- L23 `__init__(self, *, base_url: str, consumer_key: str, consumer_secret: str)` (method)
- L27 `get(self, path: str, params: dict | None=None)` (method)
- L35 `WooImporter` (class)
- L38 `__init__(self, *, base_url: str='', consumer_key: str='', consumer_secret: str='', client: Any | None=None, records: dict[str, Iterable[dict]] | None=None)` (method)
- L58 `iter_products(self)` (method)
- L74 `iter_customers(self)` (method)
- L82 `iter_orders(self)` (method)
- L90 `_run(self)` (method)
- L100 `_import_product(self, record: dict)` (method)
- L133 `_import_customer(self, record: dict)` (method)
- L151 `_import_order(self, record: dict)` (method)
- L173 `_unique_slug(seed: str)` (method)
