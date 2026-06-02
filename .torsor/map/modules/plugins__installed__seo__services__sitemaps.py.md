---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/seo/services/sitemaps.py

Symbols in `plugins/installed/seo/services/sitemaps.py`.

- L19 `_iter_author_entries(base: str)` (function) — Authors are derived from ``Metafield`` rows
- L53 `_iter_webstory_entries(base: str)` (function) — One ``/story/<slug>/`` URL per published WebStory. The webstories
- L79 `iter_sitemap_entries()` (function) — Yield entries that should appear in the sitemap. Pulls from:
- L182 `sitemap_counts()` (function) — Aggregate ``iter_sitemap_entries()`` into per-source counts +
- L252 `_sitemap_max_urls()` (function) — Read the configured per-file cap; clamp to Google's hard limit
- L265 `render_sitemap_xml()` (function) — Render the primary /sitemap.xml. Capped at
- L300 `render_sitemap_index_xml()` (function) — Sitemap index — points at every sub-sitemap. Crawlers discover
- L327 `render_news_sitemap_xml()` (function) — News sitemap for journal posts.
- L394 `render_image_sitemap_xml()` (function) — Image-only sitemap. Lists every product's primary image with its
- L442 `render_opensearch_xml()` (function) — OpenSearch description — installs the site as a Chrome tab-to-
