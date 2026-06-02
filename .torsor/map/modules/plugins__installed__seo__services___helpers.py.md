---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/seo/services/_helpers.py

Symbols in `plugins/installed/seo/services/_helpers.py`.

- L27 `strip_html(text)` (function) — Flatten HTML to plain text for meta tags, JSON-LD, and data-attrs.
- L40 `ResolvedMeta` (class) — Concrete, fallback-resolved meta values ready for rendering.
- L55 `to_html(self)` (method) — Render the meta tags as an HTML fragment for the <head>.
- L115 `_site_base_url()` (function)
- L123 `site_settings()` (function) — Return SiteSeoSettings singleton, fallback to fresh in-memory if DB empty.
- L138 `_seo_plugin_cfg()` (function) — Read seo plugin's PluginConfig JSON. Used for fields that don't
- L154 `_jsonld_dump(obj: dict)` (function)
- L158 `ai_answer_for(obj)` (function) — Return the merchant's quotable TL;DR / key-answer for ``obj``.
- L184 `_seo_plugin()` (function) — Resolve the live SEO plugin instance via the plugin registry.
