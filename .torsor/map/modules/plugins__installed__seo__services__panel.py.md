---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/seo/services/panel.py

Symbols in `plugins/installed/seo/services/panel.py`.

- L61 `_clamp_twitter(value: str)` (function)
- L66 `_robots_from_post(post)` (function) — The panel's noindex/nofollow checkboxes → a valid robots string.
- L74 `_robots_extra_from_post(post)` (function) — Advanced directives. Only non-default values are stored, so an untouched
- L95 `_sitemap_choice(value)` (function) — The stored tri-state as a form value. NULL means "platform default".
- L102 `_sitemap_from_post(post)` (function)
- L111 `_native(obj, field: str)` (function)
- L147 `_stored_values(obj)` (function) — `(values, ai_answer, robots_extra, provenance)` for a saved object.
- L203 `panel_context(obj, request=None)` (function) — Panel context for ``obj`` — stored values, or the POSTed ones on a
- L284 `_schema_editor_url(obj)` (function) — The visual structured-data editor for this object.
- L301 `_cover_url(obj)` (function) — The image a page shares when it has no share image of its own.
- L315 `_object_path(obj)` (function)
- L324 `save_object_seo(obj, post)` (function) — Upsert ``obj``'s SeoMeta override from the panel's ``seo_*`` POST fields.
- L399 `_purge_object_url(obj)` (function) — A meta change rewrites cached HTML without touching the product row, so
