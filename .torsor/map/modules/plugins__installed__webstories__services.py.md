---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:53'
updated: '2026-06-02T18:07:53'
---

# plugins/installed/webstories/services.py

Symbols in `plugins/installed/webstories/services.py`.

- L28 `_image_url_for(image_row)` (function) — Prefer the WebP variant (smaller, AMP-friendly) when present.
- L37 `_book_metafields(product)` (function) — Pull namespace='book' metafields for synopsis / author / etc.
- L59 `build_panels_for(product)` (function) — Generate panels for ``product``. Idempotent + side-effect-free.
- L128 `ensure_story(product)` (function) — Get-or-create the WebStory for ``product`` and refresh panels.
- L157 `story_path(product_slug: str)` (function)
