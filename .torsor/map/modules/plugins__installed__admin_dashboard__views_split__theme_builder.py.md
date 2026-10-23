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

# plugins/installed/admin_dashboard/views_split/theme_builder.py

Symbols in `plugins/installed/admin_dashboard/views_split/theme_builder.py`.

- L31 `_require_cms()` (function) — Every builder endpoint edits cms `Page`/`PageSection` rows, so with the
- L41 `_serialize_section_def(section)` (function)
- L52 `_serialize_row(row)` (function)
- L64 `builder(request: HttpRequest, page_id)` (function)
- L92 `api_add(request: HttpRequest, page_id)` (function) — Append a new section to a page. Returns the created row.
- L119 `api_reorder(request: HttpRequest, page_id)` (function) — Replace the sort order of every row on a page in one call.
- L148 `api_update(request: HttpRequest, page_id, row_id)` (function) — Update a row's settings or visibility.
- L173 `api_delete(request: HttpRequest, page_id, row_id)` (function)
