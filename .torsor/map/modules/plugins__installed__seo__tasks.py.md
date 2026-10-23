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

# plugins/installed/seo/tasks.py

Symbols in `plugins/installed/seo/tasks.py`.

- L17 `warm_ai_feed_task()` (function) — Rebuild /ai/products.json's first page before its cache lapses, so a crawler
- L30 `optimize_images_task(widths: str='', avif: bool=False)` (function) — Run the ``optimize_images`` batch warmer in the background and stash a
- L69 `last_image_optimize_status()` (function) — Cached status dict for the settings page (``None`` until first run).
- L80 `site_audit_task(limit: int=0)` (function) — Nightly site-wide SEO crawl — see `services/site_audit.py`.
