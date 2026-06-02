---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-02T18:23:19'
updated: '2026-06-02T18:23:19'
rules: []
---

# ADR 0002: Image-optimization controls live on the SEO dashboard, run via Celery

## Context
The image-variant pipeline (generate_image_variant, the /img/<fmt>/<width>/<path> view, and the optimize_images management command) is owned by the seo plugin. The user asked for an "optimize old images" button "in the caching settings dashboard", but there is no dedicated caching settings page — caching is plugin config consumed by storefront's caching.py template tags, not a page.

## Decision
Place the "Optimize existing images" button + last-run status on the SEO dashboard's Site SEO settings page (seo_dashboard:settings), enqueuing the optimize_images command via a Celery task (seo.optimize_images in plugins/installed/seo/tasks.py) so warming the whole back-catalogue never blocks a request. Image controls stay with the plugin that owns the pipeline — no cross-plugin coupling.

## Consequences
Image optimization is discoverable under SEO settings rather than a non-existent caching page. The task records a status dict in Django cache (key seo:image_optimize:status) that the settings page reads to show running/done/failed. Pairs with the already-shipped optimize_images batch command + optimize-on-upload (MediaAsset.from_upload).
