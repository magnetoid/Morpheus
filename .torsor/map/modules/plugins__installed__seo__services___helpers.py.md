---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/seo/services/_helpers.py

Symbols in `plugins/installed/seo/services/_helpers.py`.

- L28 `strip_html(text)` (function) — Flatten HTML to plain text for meta tags, JSON-LD, and data-attrs.
- L41 `ResolvedMeta` (class) — Concrete, fallback-resolved meta values ready for rendering.
- L57 `to_html(self)` (method) — Render the meta tags as an HTML fragment for the <head>.
- L118 `_site_base_url()` (function)
- L122 `site_settings()` (function) — Return SiteSeoSettings singleton, fallback to fresh in-memory if DB empty.
- L137 `_seo_plugin_cfg()` (function) — Read seo plugin's PluginConfig JSON. Used for fields that don't
- L153 `_jsonld_dump(obj: dict)` (function)
- L157 `ai_answer_for(obj)` (function) — Return the merchant's quotable TL;DR / key-answer for ``obj``.
- L183 `_seo_plugin()` (function) — Resolve the live SEO plugin instance via the plugin registry.
