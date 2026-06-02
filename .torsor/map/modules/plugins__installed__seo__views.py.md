---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/seo/views.py

Symbols in `plugins/installed/seo/views.py`.

- L41 `_cache_headers(response: HttpResponse, last_modified=None)` (function) — Apply the shared public-crawler cache policy to a response.
- L66 `_sitemap_last_modified()` (function) — Best-effort last-modified for sitemap surfaces.
- L89 `sitemap_xml(request: HttpRequest)` (function)
- L94 `robots_txt(request: HttpRequest)` (function)
- L101 `llms_txt(request: HttpRequest)` (function)
- L109 `llms_full_txt(request: HttpRequest)` (function)
- L117 `journal_rss(request: HttpRequest)` (function) — RSS 2.0 feed for /journal/. Top 50 published posts, ordered by publish_at.
- L126 `journal_atom(request: HttpRequest)` (function) — Atom 1.0 feed for /journal/. Same source set as the RSS feed.
- L135 `ai_products_feed(request: HttpRequest)` (function)
- L153 `product_markdown(request: HttpRequest, slug: str)` (function) — Markdown rendering of a product — the LLM-friendly view.
- L174 `image_sitemap_xml(request: HttpRequest)` (function) — Image-only sitemap. Discovered by AI image-search engines for
- L194 `sitemap_index_xml(request: HttpRequest)` (function) — Sitemap index — entry-point that lists every sub-sitemap.
- L207 `news_sitemap_xml(request: HttpRequest)` (function) — News sitemap — journal posts in the last 48h. Empty urlset
- L228 `_seo_flag(key: str, default: bool)` (function) — Read a boolean SEO plugin config value defensively.
- L250 `_maybe_ping_sitemap_change()` (function) — Notify Google + Bing + IndexNow when the sitemap changed.
- L278 `opensearch_xml(request: HttpRequest)` (function) — OpenSearch description for browser tab-to-search engines.
- L290 `image_variant(request: HttpRequest, fmt: str, width: int, path: str)` (function) — Serve a resized WebP/AVIF variant of an image under MEDIA_ROOT.
- L321 `security_txt(request: HttpRequest)` (function) — Serve /.well-known/security.txt per RFC 9116.
- L361 `indexnow_keyfile(request: HttpRequest, key: str)` (function) — Serve the IndexNow key as plain text so api.indexnow.org can
- L373 `web_vitals_beacon(request: HttpRequest)` (function) — Receive Real-User-Metrics from the storefront's web-vitals JS.
- L417 `seo_overview(request)` (function)
- L504 `_cwv_summary()` (function) — Aggregate the last 1000 web-vitals beacon reports into p75 per
- L539 `seo_settings_page(request)` (function)
- L646 `not_found_log(request)` (function)
- L655 `not_found_create_redirect(request, log_id)` (function)
- L677 `audit_page(request)` (function)
- L691 `keywords_page(request)` (function)
- L711 `bulk_meta(request)` (function) — Bulk-edit SEO titles + descriptions across products.
- L809 `sitemap_page(request)` (function) — Sitemap dashboard — single page for every sitemap surface,
- L1044 `redirects_page(request)` (function) — List + create + edit + delete 301/302 Redirect rules.
- L1103 `seo_inspector(request)` (function) — Paste-a-slug, see-everything inspector for a single Product /
- L1342 `not_found_dismiss(request, pk)` (function) — Mark a NotFoundLog row resolved without creating a redirect.
