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

# plugins/installed/seo/services/_helpers.py

Symbols in `plugins/installed/seo/services/_helpers.py`.

- L28 `strip_html(text)` (function) — Flatten HTML to plain text for meta tags, JSON-LD, and data-attrs.
- L41 `ResolvedMeta` (class) — Concrete, fallback-resolved meta values ready for rendering.
- L74 `to_html(self)` (method) — Render the meta tags as an HTML fragment for the <head>.
- L154 `_site_base_url()` (function)
- L158 `site_settings()` (function) — The site-wide SEO settings row.
- L188 `_seo_plugin_cfg()` (function) — Read seo plugin's PluginConfig JSON. Used for fields that don't
- L218 `_jsonld_dump(obj: dict)` (function)
- L222 `ai_answer_for(obj)` (function) — Return the merchant's quotable TL;DR / key-answer for ``obj``.
- L260 `_plugin(name: str)` (function) — Resolve any live plugin instance by name via the registry.
- L283 `_seo_plugin()` (function) — Resolve the live SEO plugin instance via the plugin registry.
- L288 `_return_window_days()` (function) — The store's real return window (days) from the returns_portal plugin, or
