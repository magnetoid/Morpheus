---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/catalog/search/dispatcher.py

Symbols in `plugins/installed/catalog/search/dispatcher.py`.

- L19 `SearchResult` (class) — Backend-agnostic shape.
- L29 `get_backend()` (function) — Return the active backend name.
- L41 `search(q: str, *, page: int=1, per_page: int=24, filter_by: str='', sort_by: str='')` (function) — Run a search via the active backend. Falls back to Django on any
