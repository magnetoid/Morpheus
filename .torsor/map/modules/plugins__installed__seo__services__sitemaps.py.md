---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/seo/services/sitemaps.py

Symbols in `plugins/installed/seo/services/sitemaps.py`.

- L22 `_iter_author_entries(base: str)` (function) — Authors are derived from ``Metafield`` rows
- L48 `_iter_webstory_entries(base: str)` (function) — One ``/story/<slug>/`` URL per published WebStory. The webstories
- L74 `_iter_book_facet_entries(base: str)` (function) — Book-taxonomy landing pages owned by the book_product plugin:
- L119 `_iter_cms_page_entries(base: str)` (function) — Every *published* CMS page, so any page a merchant adds shows up in the
- L147 `iter_sitemap_entries()` (function) — Yield entries that should appear in the sitemap. Pulls from:
- L239 `sitemap_counts()` (function) — Aggregate ``iter_sitemap_entries()`` into per-source counts +
- L316 `regenerate_sitemap(triggered_by: str='dashboard')` (function) — Re-publish the sitemap. It's rendered live on every request, so
- L354 `_sitemap_max_urls()` (function) — Read the configured per-file cap; clamp to Google's hard limit
- L367 `render_sitemap_xml()` (function) — Render the primary /sitemap.xml. Capped at
- L402 `render_sitemap_index_xml()` (function) — Sitemap index — points at every sub-sitemap. Crawlers discover
- L429 `render_news_sitemap_xml()` (function) — News sitemap for journal posts.
- L496 `render_image_sitemap_xml()` (function) — Image-only sitemap. Lists every product's primary image with its
- L544 `render_opensearch_xml()` (function) — OpenSearch description — installs the site as a Chrome tab-to-
