---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/storefront/templatetags/caching.py

Symbols in `plugins/installed/storefront/templatetags/caching.py`.

- L28 `_storefront_config()` (function)
- L40 `_split_lines(raw: str)` (function)
- L45 `caching_resource_hints()` (function) — Emit <link rel="preconnect"> + <link rel="dns-prefetch"> tags.
- L58 `caching_preload_fonts()` (function) — Emit <link rel="preload" as="font"> for fonts that should load
- L81 `caching_font_display()` (function) — Emit a <style> block that forces a font-display value on
- L99 `caching_service_worker_register()` (function) — Register the storefront service worker if the merchant
- L128 `caching_img_loading_attr()` (function) — Returns ``lazy`` when lazy-load is enabled, else empty string.
- L142 `caching_preload_lcp(url: str, sizes: str='', srcset: str='')` (function) — Emit ``<link rel="preload" as="image">`` for the LCP image.
- L170 `caching_script_defer_attr()` (function) — Returns ``defer`` when defer_non_critical_js is on, else empty.
