---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/admin_dashboard/views_split/settings.py

Symbols in `plugins/installed/admin_dashboard/views_split/settings.py`.

- L19 `_panels_by_category()` (function) — Index every active plugin's SettingsPanel by its category slug.
- L42 `_build_panel_fields(plugin_instance, schema: dict)` (function) — Schema → list of form-field dicts (matches plugin_settings.html shape).
- L66 `settings_view(request: HttpRequest)` (function) — Settings hub — Shopify-style category index.
- L126 `_core_form_for(category: str)` (function) — Return (form_class, title, description) for a category, or None.
- L138 `settings_ai_probe(request: HttpRequest)` (function) — JSON endpoint backing the "Fetch models" + "Test connection" buttons.
- L239 `settings_caching(request: HttpRequest)` (function) — Unified caching dashboard — Django cache backend status, Redis
- L583 `settings_ai(request: HttpRequest)` (function) — Custom AI providers settings page — card per provider.
- L698 `settings_category(request: HttpRequest, category: str)` (function) — Render every plugin SettingsPanel that belongs to one category.
- L865 `_filesystem_default(key: str)` (function) — Read the shipped default body so the editor can show / restore it.
- L889 `email_templates_list(request: HttpRequest)` (function) — Show every transactional email template, edited or not.
- L918 `email_template_edit(request: HttpRequest, key: str)` (function) — Edit one template. Reset = delete the row → falls back to filesystem default.
