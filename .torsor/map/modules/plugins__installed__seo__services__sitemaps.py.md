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

# plugins/installed/seo/services/sitemaps.py

Symbols in `plugins/installed/seo/services/sitemaps.py`.

- L22 `_app_active(name: str)` (function) — Whether the app that SERVES a family of urls is on right now.
- L38 `_iter_author_entries(base: str)` (function) — ``/author/<slug>/`` for every author with at least one ACTIVE book.
- L69 `_iter_webstory_entries(base: str)` (function) — One ``/story/<slug>/`` URL per published WebStory. Stories are
- L99 `_iter_book_facet_entries(base: str)` (function) — Book-taxonomy landing pages owned by the book_product plugin:
- L169 `_iter_cms_page_entries(base: str)` (function) — Every *published* CMS page, so any page a merchant adds shows up in the
- L208 `_seo_overrides(model)` (function) — `{object_id: (sitemap_include, robots)}` for one model, in ONE query.
- L233 `_in_sitemap(overrides: dict, obj)` (function) — Whether this object's URL belongs in the sitemap.
- L241 `iter_sitemap_entries()` (function) — Yield entries that should appear in the sitemap. Pulls from:
- L357 `_normalize_contributed_entry(e: dict)` (function) — SITEMAP_URLS subscribers may hand back raw ``date``/``datetime``
- L374 `_merged_sitemap_entries()` (function) — Native ``iter_sitemap_entries()`` output + anything folded in through
- L407 `sitemap_counts()` (function) — Aggregate every URL the sitemap serves into per-source counts +
- L495 `regenerate_sitemap(triggered_by: str='dashboard')` (function) — Re-publish the sitemap. It's rendered live on every request, so
- L537 `_sitemap_max_urls()` (function) — Read the configured per-file cap; clamp to Google's hard limit
- L550 `render_sitemap_xml()` (function) — Render the primary /sitemap.xml. Capped at
- L589 `render_sitemap_index_xml()` (function) — Sitemap index — points at every sub-sitemap. Crawlers discover
- L633 `render_news_sitemap_xml()` (function) — News sitemap for journal posts.
- L700 `render_image_sitemap_xml()` (function) — Image-only sitemap. Lists every product's primary image with its
- L747 `render_opensearch_xml()` (function) — OpenSearch description — installs the site as a Chrome tab-to-
