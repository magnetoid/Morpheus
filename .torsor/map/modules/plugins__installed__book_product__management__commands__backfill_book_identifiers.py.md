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

# plugins/installed/book_product/management/commands/backfill_book_identifiers.py

Symbols in `plugins/installed/book_product/management/commands/backfill_book_identifiers.py`.

- L29 `_norm(s: str)` (function)
- L33 `_surname(author: str)` (function)
- L38 `pick_work(title: str, author: str, docs: list[dict])` (function) — Best conservative match → (olid, oclc). Author surname must match and the
- L66 `_lookup(title: str, author: str, timeout: int=15)` (function)
- L75 `Command` (class)
- L78 `add_arguments(self, parser)` (method)
- L86 `handle(self, *args, **opts)` (method)
