---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/seo/services/images.py

Symbols in `plugins/installed/seo/services/images.py`.

- L18 `variant_cache_abs(rel: str, width: int, fmt: str)` (function) — Absolute path of the cached variant for ``(rel, width, fmt)``.
- L33 `parse_image_variant_path(fmt: str, width: int, path: str)` (function) — Validate + resolve a public image variant request.
- L57 `generate_image_variant(src_abs: str, cache_abs: str, *, width: int, fmt: str)` (function) — Pillow-resize ``src_abs`` to ``width`` px wide at quality 80,
