---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/webstories/services.py

Symbols in `plugins/installed/webstories/services.py`.

- L28 `_image_url_for(image_row)` (function) — Prefer the WebP variant (smaller, AMP-friendly) when present.
- L37 `_book_metafields(product)` (function) — Book attributes (synopsis / author / …) for the story panels.
- L51 `build_panels_for(product)` (function) — Generate panels for ``product``. Idempotent + side-effect-free.
- L120 `ensure_story(product)` (function) — Get-or-create the WebStory for ``product`` and refresh panels.
- L149 `story_path(product_slug: str)` (function)
