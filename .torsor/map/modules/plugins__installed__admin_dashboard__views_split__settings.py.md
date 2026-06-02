---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/admin_dashboard/views_split/settings.py

Symbols in `plugins/installed/admin_dashboard/views_split/settings.py`.

- L26 `_panels_by_category()` (function) — Index every active plugin's SettingsPanel by its category slug.
- L47 `_build_panel_fields(plugin_instance, schema: dict)` (function) — Schema → list of form-field dicts (matches plugin_settings.html shape).
- L69 `settings_view(request: HttpRequest)` (function) — Settings hub — Shopify-style category index.
- L118 `_core_form_for(category: str)` (function) — Return (form_class, title, description) for a category, or None.
- L129 `settings_ai_probe(request: HttpRequest)` (function) — JSON endpoint backing the "Fetch models" + "Test connection" buttons.
- L228 `settings_caching(request: HttpRequest)` (function) — Unified caching dashboard — Django cache backend status, Redis
- L439 `settings_ai(request: HttpRequest)` (function) — Custom AI providers settings page — card per provider.
- L551 `settings_category(request: HttpRequest, category: str)` (function) — Render every plugin SettingsPanel that belongs to one category.
- L661 `_filesystem_default(key: str)` (function) — Read the shipped default body so the editor can show / restore it.
- L681 `email_templates_list(request: HttpRequest)` (function) — Show every transactional email template, edited or not.
- L704 `email_template_edit(request: HttpRequest, key: str)` (function) — Edit one template. Reset = delete the row → falls back to filesystem default.
