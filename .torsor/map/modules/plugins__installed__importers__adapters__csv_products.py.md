---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/importers/adapters/csv_products.py

Symbols in `plugins/installed/importers/adapters/csv_products.py`.

- L31 `CsvProductImporter` (class)
- L34 `__init__(self, *, file: IO[str] | None=None, rows: Iterable[dict] | None=None)` (method)
- L43 `_run(self)` (method)
- L54 `_upsert_row(self, row: dict, *, Product, Category)` (method)
- L93 `_money(value, currency: str, *, allow_blank: bool=False)` (function)
- L102 `_bool(value)` (function)
- L108 `export_products_csv(*, queryset=None)` (function) — Render a queryset of Product to a CSV string.
