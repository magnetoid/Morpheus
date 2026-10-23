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

# plugins/installed/seo/views.py

Symbols in `plugins/installed/seo/views.py`.

- L48 `_cache_headers(response: HttpResponse, last_modified=None)` (function) — Apply the shared public-crawler cache policy to a response.
- L73 `_sitemap_last_modified()` (function) — Best-effort last-modified for sitemap surfaces.
- L106 `_hidden_document(body: str)` (function) — An empty sitemap for a store hidden until launch — never cached long.
- L113 `sitemap_xml(request: HttpRequest)` (function)
- L120 `robots_txt(request: HttpRequest)` (function)
- L127 `llms_txt(request: HttpRequest)` (function)
- L135 `llms_full_txt(request: HttpRequest)` (function)
- L143 `agents_md(request: HttpRequest)` (function) — /agents.md — the agent-onboarding manifest (gated by the same
- L153 `journal_rss(request: HttpRequest)` (function) — RSS 2.0 feed for /journal/. Top 50 published posts, ordered by publish_at.
- L162 `journal_atom(request: HttpRequest)` (function) — Atom 1.0 feed for /journal/. Same source set as the RSS feed.
- L171 `ai_products_feed(request: HttpRequest)` (function)
- L194 `product_markdown(request: HttpRequest, slug: str)` (function) — Markdown rendering of a product — the LLM-friendly view.
- L217 `image_sitemap_xml(request: HttpRequest)` (function) — Image-only sitemap. Discovered by AI image-search engines for
- L237 `sitemap_index_xml(request: HttpRequest)` (function) — Sitemap index — entry-point that lists every sub-sitemap.
- L252 `news_sitemap_xml(request: HttpRequest)` (function) — News sitemap — journal posts in the last 48h. Empty urlset
- L273 `_seo_flag(key: str, default: bool)` (function) — Read a boolean SEO plugin config value defensively.
- L295 `_maybe_ping_sitemap_change()` (function) — Notify Google + Bing + IndexNow when the sitemap changed.
- L317 `opensearch_xml(request: HttpRequest)` (function) — OpenSearch description for browser tab-to-search engines.
- L329 `image_variant(request: HttpRequest, fmt: str, width: int, path: str)` (function) — Serve a resized WebP/AVIF variant of an image under MEDIA_ROOT.
- L362 `security_txt(request: HttpRequest)` (function) — Serve /.well-known/security.txt per RFC 9116.
- L402 `indexnow_keyfile(request: HttpRequest, key: str)` (function) — Serve the IndexNow key as plain text so api.indexnow.org can
- L414 `web_vitals_beacon(request: HttpRequest)` (function) — Receive Real-User-Metrics from the storefront's web-vitals JS.
- L459 `seo_overview(request)` (function)
- L556 `seo_site_audit_run(request)` (function) — Queue a fresh site-wide crawl.
- L591 `seo_settings_page(request)` (function)
- L704 `not_found_log(request)` (function) — The 404 monitor.
- L735 `not_found_create_redirect(request, log_id)` (function)
- L758 `audit_page(request)` (function)
- L777 `keywords_page(request)` (function)
- L802 `bulk_meta(request)` (function) — Bulk-edit SEO titles + descriptions across products.
- L905 `sitemap_page(request)` (function) — Sitemap dashboard — single page for every sitemap surface,
- L1158 `redirects_page(request)` (function) — Create, edit, delete and import the redirect rules.
- L1261 `index_rules_page(request)` (function) — Decide which query-parameter URLs of a listing deserve to be indexed.
- L1360 `_probe_url(raw: str)` (function) — What the index rules do to one URL's query string.
- L1390 `_dropped_params(before: str, after: str)` (function)
- L1397 `_legacy_noindex_params_for_display()` (function) — Parameters still coming from the old settings field, if any.
- L1414 `seo_inspector(request)` (function) — Paste-a-slug, see-everything inspector for a single Product /
- L1655 `not_found_dismiss(request, pk)` (function) — Mark a NotFoundLog row resolved without creating a redirect.
- L1680 `schema_index(request: HttpRequest)` (function)
- L1723 `schema_editor(request: HttpRequest, app_label: str, model: str, pk: str)` (function)
- L1792 `templates_page(request)` (function) — Title/description patterns per page kind — Dashboard → SEO → Templates.
