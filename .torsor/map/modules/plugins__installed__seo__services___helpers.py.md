---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/seo/services/_helpers.py

Symbols in `plugins/installed/seo/services/_helpers.py`.

- L27 `strip_html(text)` (function) — Flatten HTML to plain text for meta tags, JSON-LD, and data-attrs.
- L40 `ResolvedMeta` (class) — Concrete, fallback-resolved meta values ready for rendering.
- L56 `to_html(self)` (method) — Render the meta tags as an HTML fragment for the <head>.
- L117 `_site_base_url()` (function)
- L125 `site_settings()` (function) — Return SiteSeoSettings singleton, fallback to fresh in-memory if DB empty.
- L140 `_seo_plugin_cfg()` (function) — Read seo plugin's PluginConfig JSON. Used for fields that don't
- L156 `_jsonld_dump(obj: dict)` (function)
- L160 `ai_answer_for(obj)` (function) — Return the merchant's quotable TL;DR / key-answer for ``obj``.
- L186 `_seo_plugin()` (function) — Resolve the live SEO plugin instance via the plugin registry.
