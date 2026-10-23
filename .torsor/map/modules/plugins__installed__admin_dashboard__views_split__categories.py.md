---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# plugins/installed/admin_dashboard/views_split/categories.py

Symbols in `plugins/installed/admin_dashboard/views_split/categories.py`.

- L32 `categories_list(request: HttpRequest)` (function)
- L110 `category_new(request: HttpRequest)` (function) — Create a category in the dashboard (the stock admin is not mounted live).
- L149 `category_edit(request: HttpRequest, category_id: str)` (function)
- L191 `category_quick_create(request: HttpRequest)` (function) — Create a category from the product form's category picker; JSON in, JSON out.
- L243 `_picker_entry(category, *, existing: bool)` (function) — What the category picker needs to place a category in its tree.
