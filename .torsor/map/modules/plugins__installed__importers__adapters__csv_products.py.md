---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/importers/adapters/csv_products.py

Symbols in `plugins/installed/importers/adapters/csv_products.py`.

- L43 `CsvProductImporter` (class)
- L46 `__init__(self, *, file: IO[str] | None=None, rows: Iterable[dict] | None=None)` (method)
- L55 `_run(self)` (method)
- L67 `_upsert_row(self, row: dict, *, Product, Category)` (method)
- L112 `_money(value, currency: str, *, allow_blank: bool=False)` (function)
- L121 `_bool(value)` (function)
- L127 `export_products_csv(*, queryset=None)` (function) — Render a queryset of Product to a CSV string.
