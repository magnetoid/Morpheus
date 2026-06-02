---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/product_videos/sanitize.py

Symbols in `plugins/installed/product_videos/sanitize.py`.

- L46 `_host_allowed(src: str)` (function)
- L56 `_scheme_safe(src: str)` (function) — Reject javascript:, data:, vbscript:, file:, …
- L61 `sanitize_embed_html(raw: str)` (function) — Return a sanitized `<iframe>` from `raw`, or empty string if no
