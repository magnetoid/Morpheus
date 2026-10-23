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

# plugins/installed/cms/dashboard.py

Symbols in `plugins/installed/cms/dashboard.py`.

- L19 `_safe_list(model_path, *, order_by='-updated_at', limit=200)` (function)
- L29 `_hardcoded_pages()` (function) — Storefront pages that live in CODE, declared by ACTIVE plugins via an
- L63 `pages_list(request)` (function)
- L73 `blocks_list(request)` (function)
- L79 `menus_list(request)` (function)
- L85 `forms_list(request)` (function)
- L96 `_parse_publish_at(raw)` (function) — A datetime-local field value ('YYYY-MM-DDTHH:MM') → aware datetime, or None.
- L106 `_apply_editorial_metadata(meta: dict, post)` (function) — Fold the page form's metadata-backed controls into ``meta``: the
- L141 `_meta_list_text(value)` (function) — A metadata list (author_same_as / citations) → newline-joined text for
- L149 `_page_form_context(request, page, *, creating)` (function)
- L170 `_page_form_cards(request, page)` (function) — Cards contributed into the page form (PAGE_FORM_CARDS) — the SEO panel
- L200 `page_edit(request, page_id=None)` (function) — Create (page_id is None) or edit a CMS Page.
- L285 `page_duplicate(request, page_id)` (function)
- L310 `page_delete(request, page_id)` (function)
- L330 `_bust_menu_cache()` (function)
- L339 `_menu_item_action(request, menu, action)` (function) — Handle the per-item POST actions (add/edit/delete/move) for menu_edit.
- L392 `menu_edit(request, menu_id=None)` (function) — Create (menu_id None) or edit a Menu + its items. POST dispatches on an
- L443 `menu_delete(request, menu_id)` (function)
