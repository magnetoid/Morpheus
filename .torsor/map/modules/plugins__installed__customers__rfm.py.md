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

# plugins/installed/customers/rfm.py

Symbols in `plugins/installed/customers/rfm.py`.

- L18 `classify(r: int, f: int, m: int, purchase_count: int, is_recent: bool)` (function) — Map RFM quintile scores → a named segment. Pure + exhaustively tested.
- L33 `_quintile_scores(pairs: list)` (function) — pairs = [(key, sortable_value)] → {key: 1-5}. Lowest value → 1, highest → 5.
- L40 `recompute_all()` (function) — Score every customer with ≥1 order, upsert CustomerSegment, log + fire on flip.
