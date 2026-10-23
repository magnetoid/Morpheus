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

# plugins/installed/dsers/services/export.py

Symbols in `plugins/installed/dsers/services/export.py`.

- L69 `_config()` (function)
- L76 `eligible_orders()` (function) — Paid, confirmed/processing, never exported, with at least one shippable line.
- L81 `order_rows(order, memo: str)` (function)
- L114 `export_orders(orders)` (function) — Build the `import_orders` CSV for ``orders`` and mark each as exported.
- L147 `export_products()` (function) — The `import_products` mapping file: every supplier link, one row each.
