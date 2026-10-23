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

# plugins/installed/seo/tests/test_site_audit.py

Symbols in `plugins/installed/seo/tests/test_site_audit.py`.

- L18 `_codes(report)` (function)
- L22 `_finding(report, code)` (function)
- L26 `SiteAuditTests` (class)
- L28 `setUpTestData(cls)` (method)
- L43 `test_a_scan_reports_pages_and_a_score(self)` (method)
- L49 `test_two_pages_sharing_a_title_are_reported(self)` (method)
- L65 `test_coverage_is_measured_from_what_rendered(self)` (method)
- L80 `test_a_single_language_store_is_not_nagged_about_hreflang(self)` (method)
- L84 `test_a_multilingual_store_is_told_when_alternates_are_missing(self)` (method)
- L93 `test_findings_are_ordered_worst_first(self)` (method)
- L99 `test_every_finding_explains_itself(self)` (method)
- L108 `test_a_redirecting_sitemap_url_is_critical(self)` (method)
- L127 `CacheTests` (class)
- L128 `test_nothing_cached_reads_as_no_scan_yet(self)` (method)
- L134 `test_a_run_is_stored_and_read_back(self)` (method)
- L139 `OverviewPageTests` (class)
- L140 `setUp(self)` (method)
- L149 `test_the_page_renders_before_any_scan_has_run(self)` (method)
- L157 `test_findings_render_once_a_scan_exists(self)` (method)
- L164 `test_the_run_endpoint_only_accepts_post(self)` (method)
- L171 `HttpsRedirectTests` (class) — The audit must work on a store that forces HTTPS — i.e. all of them.
- L181 `test_forced_https_is_not_mistaken_for_a_broken_sitemap(self)` (method)
- L194 `ContributedCorpusTests` (class) — The audit and the sitemap dashboard must see the SAME urls as /sitemap.xml.
- L204 `_with_contribution(self, fn)` (method)
- L216 `test_audit_covers_contributed_urls(self)` (method)
- L222 `test_sitemap_counts_matches_what_the_sitemap_serves(self)` (method)
- L238 `test_a_contributed_url_is_not_counted_as_hand_written(self)` (method)
