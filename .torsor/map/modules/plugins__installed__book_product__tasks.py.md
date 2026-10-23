---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/book_product/tasks.py

Symbols in `plugins/installed/book_product/tasks.py`.

- L33 `missing_copy_queryset(kind: str)` (function) — The terms the backfill will actually write, most-stocked first.
- L61 `backfill_taxonomy_copy(kind: str, limit: int=25)` (function) — Write intro + SEO for `limit` curated terms of `kind` that lack it.
- L92 `_write_copy(kind: str, targets: list)` (function) — Generate + save copy for each target. Returns (written, skipped).
