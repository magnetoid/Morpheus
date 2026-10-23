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

# plugins/installed/seo/tests/test_seo.py

Symbols in `plugins/installed/seo/tests/test_seo.py`.

- L23 `ResolveMetaTests` (class)
- L24 `test_returns_fallbacks_when_no_meta(self)` (method)
- L33 `test_overrides_with_seo_meta_row(self)` (method)
- L66 `test_og_image_falls_back_to_store_default_social_image(self)` (method) — With no per-page/SEO override, og:image uses the core-wide default
- L75 `test_to_html_emits_required_tags(self)` (method)
- L95 `AutofillTests` (class)
- L96 `test_autofill_for_product(self)` (method)
- L111 `test_autofill_stores_clean_title_without_brand(self)` (method)
- L125 `DocumentTitleTests` (class)
- L126 `test_brand_falls_back_to_store_name(self)` (method)
- L134 `test_document_title_applies_template_and_brand(self)` (method)
- L144 `test_clamping_a_long_title_never_cuts_through_a_word(self)` (method) — The 60-char clamp sliced the finished string, so the brand was the
- L164 `test_object_page_gets_branded_document_title(self)` (method)
- L182 `RedirectTests` (class)
- L183 `test_resolve_redirect_returns_target(self)` (method)
- L193 `test_resolve_unknown_path_returns_none(self)` (method)
- L196 `test_redirect_increments_hit_count(self)` (method) — Counting moved OUT of resolve_redirect and into the middleware.
- L216 `MiddlewareTests` (class)
- L217 `setUp(self)` (method)
- L226 `test_middleware_redirects_known_path(self)` (method)
- L232 `test_middleware_passes_through_skipped_prefixes(self)` (method)
- L244 `SitemapTests` (class)
- L245 `test_sitemap_renders_when_empty_catalog(self)` (method)
- L250 `test_sitemap_includes_active_products(self)` (method)
- L261 `test_robots_lists_sitemap(self)` (method)
- L281 `DeepSeoServicesTests` (class)
- L282 `test_render_llms_txt(self)` (method)
- L289 `test_render_agents_md_has_discovery_and_endpoints(self)` (method)
- L302 `test_agents_md_endpoints_section_vanishes_when_agent_mcp_disabled(self)` (method)
- L315 `test_agents_md_view_404s_when_expose_disabled(self)` (method)
- L323 `test_organization_jsonld_returns_none_when_no_org_name(self)` (method)
- L329 `test_organization_jsonld_with_settings(self)` (method)
- L350 `test_404_log_records_and_dedupes(self)` (method)
- L360 `test_audit_product_low_score_when_empty(self)` (method)
- L379 `DeepSeoAgentToolsTests` (class)
- L380 `test_tools_registered(self)` (method)
