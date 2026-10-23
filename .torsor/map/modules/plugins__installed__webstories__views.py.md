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

# plugins/installed/webstories/views.py

Symbols in `plugins/installed/webstories/views.py`.

- L33 `_cache_headers(response: HttpResponse, last_modified=None)` (function)
- L41 `_site_settings()` (function)
- L54 `_site_base_url(request: HttpRequest)` (function)
- L58 `_absolute(url: str, base: str)` (function)
- L67 `_square_raster_url(img)` (function) — `img`'s URL when Google accepts it as a story's publisher logo, else ``''``.
- L77 `_publisher_logo_url(settings_row, base: str)` (function) — A square raster image of at least 96 px — Google's rule for a story's logo.
- L99 `_current_story(product, story)` (function) — ``story``, rebuilt first when an older builder made it (fail-soft).
- L112 `story_page(request: HttpRequest, slug: str)` (function) — Render the AMP Web Story document for a product.
- L173 `story_index(request: HttpRequest)` (function) — List every published Web Story whose product is still active.
