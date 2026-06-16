---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/product_videos/sanitize.py

Symbols in `plugins/installed/product_videos/sanitize.py`.

- L54 `_host_allowed(src: str)` (function)
- L64 `_scheme_safe(src: str)` (function) — Reject javascript:, data:, vbscript:, file:, …
- L69 `sanitize_embed_html(raw: str)` (function) — Return a sanitized `<iframe>` from `raw`, or empty string if no
