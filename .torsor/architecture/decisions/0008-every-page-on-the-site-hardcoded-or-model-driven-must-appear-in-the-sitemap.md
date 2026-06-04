---
type: decision
status: accepted
tags:
- adr
links: []
created: '2026-06-04T23:46:03'
updated: '2026-06-04T23:46:03'
rules:
- id: sitemap-covers-all-pages
  pattern: urlpatterns|def .*_detail|path\(
  message: New public-facing route? Ensure its URLs are emitted by iter_sitemap_entries()
    in seo/services/sitemaps.py (add an _iter_*_entries generator). Every page, hardcoded
    or model-driven, belongs in the sitemap.
---

# ADR 0008: Every page on the site — hardcoded or model-driven — must appear in the sitemap

## Context
The sitemap only listed journal CMS pages (metadata.category=='journal'); standalone CMS pages at /p/<slug>/ and book-taxonomy landing pages (publisher/series/imprint/format/language from the book_product plugin) were missing. When a merchant adds a page or a new product-app taxonomy, its URL must be discoverable.

## Decision
iter_sitemap_entries() must enumerate ALL publicly reachable URLs: every active model-backed surface (products, categories, collections, vendors, authors, book taxonomies), every published CMS page (journal → /journal/<slug>/, others → /p/<slug>/ via _iter_cms_page_entries), plus the hardcoded static editorial routes. New URL-producing features add an _iter_*_entries() generator (fail-soft, active/published only, no dead URLs). Per sitemaps.org: lastmod is the signal Google uses (keep it accurate); changefreq/priority are advisory; 50k URLs / 50MB per file cap; canonical/indexable URLs only.

## Consequences
Adding a page or taxonomy auto-appears in the sitemap. A new public route without a corresponding sitemap entry is a bug. Counts surface on the SEO → Sitemap dashboard; `manage.py regenerate_sitemap` / the Regenerate button / Linda's seo.regenerate_sitemap recount + purge CDN + ping crawlers.
