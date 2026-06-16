---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
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
- L106 `_page_seo(page)` (function) — (title, description) from the page's SeoMeta override, or ('', '').
- L123 `_save_page_seo(page, meta_title, meta_description)` (function) — Upsert the page's SeoMeta override (seo plugin, generic FK). Only writes
- L144 `_page_form_context(request, page, *, creating)` (function)
- L164 `page_edit(request, page_id=None)` (function) — Create (page_id is None) or edit a CMS Page.
- L245 `page_duplicate(request, page_id)` (function)
- L270 `page_delete(request, page_id)` (function)
- L290 `_bust_menu_cache()` (function)
- L299 `_menu_item_action(request, menu, action)` (function) — Handle the per-item POST actions (add/edit/delete/move) for menu_edit.
- L352 `menu_edit(request, menu_id=None)` (function) — Create (menu_id None) or edit a Menu + its items. POST dispatches on an
- L403 `menu_delete(request, menu_id)` (function)
