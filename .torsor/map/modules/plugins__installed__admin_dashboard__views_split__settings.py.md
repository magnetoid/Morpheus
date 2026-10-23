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

# plugins/installed/admin_dashboard/views_split/settings.py

Symbols in `plugins/installed/admin_dashboard/views_split/settings.py`.

- L20 `_panels_by_category()` (function) — Index every active plugin's SettingsPanel by its category slug.
- L43 `_build_panel_fields(plugin_instance, schema: dict)` (function) — Schema → list of form-field dicts (matches plugin_settings.html shape).
- L81 `settings_view(request: HttpRequest)` (function) — Settings hub — Shopify-style category index.
- L151 `_core_form_for(category: str)` (function) — Return (form_class, title, description) for a category, or None.
- L164 `settings_ai_probe(request: HttpRequest)` (function) — JSON endpoint backing the "Fetch models" + "Test connection" buttons.
- L219 `settings_ai_disconnect(request: HttpRequest)` (function) — Disconnect a provider — clears its api_key/base_url/model so it leaves
- L395 `settings_caching(request: HttpRequest)` (function) — Unified caching dashboard — Django cache backend status, Redis
- L747 `_ai_key_fingerprint(key: str)` (function) — A safe, recognisable hint for a stored API key — never the full secret.
- L758 `_ai_usage_summary(days: int=30)` (function) — Store-wide LLM token usage + estimated spend over the last `days`,
- L820 `settings_ai(request: HttpRequest)` (function) — Custom AI providers settings page — card per provider.
- L1030 `settings_category(request: HttpRequest, category: str)` (function) — Render every plugin SettingsPanel that belongs to one category.
- L1223 `_filesystem_default(key: str)` (function) — Read the shipped default body so the editor can show / restore it.
- L1258 `_email_template_defs()` (function) — (key, label, default_subject, group) for every template in the central
- L1276 `email_templates_list(request: HttpRequest)` (function) — Central email-templates list — core + every plugin's contributed
- L1316 `email_template_edit(request: HttpRequest, key: str)` (function) — Edit one template. Reset = delete the row → falls back to filesystem default.
