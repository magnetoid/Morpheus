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

# plugins/installed/seo/tests/test_redirects_engine.py

Symbols in `plugins/installed/seo/tests/test_redirects_engine.py`.

- L25 `PrecedenceTests` (class)
- L26 `setUp(self)` (method)
- L29 `test_exact_beats_prefix_and_prefix_beats_regex(self)` (method) — The whole reason match types are ordered.
- L50 `test_longest_prefix_wins(self)` (method)
- L59 `test_regex_rule_can_capture_and_expand(self)` (method)
- L67 `test_an_invalid_regex_costs_only_its_own_rule(self)` (method) — A merchant can type a broken pattern; every other request must live.
- L75 `test_410_resolves_with_no_target(self)` (method)
- L80 `NormalisationTests` (class)
- L81 `setUp(self)` (method)
- L84 `test_a_pasted_full_url_still_matches_the_path(self)` (method) — Merchants paste what their analytics gave them, which is a full URL.
- L92 `test_a_bare_slug_gets_a_leading_slash(self)` (method)
- L95 `test_a_regex_rule_is_not_normalised(self)` (method) — Normalising a pattern would eat the anchors that make it work.
- L103 `ChainTests` (class)
- L104 `setUp(self)` (method)
- L107 `test_a_chain_is_collapsed_on_write(self)` (method) — A→B→C costs crawl budget and loses a little authority per hop, and it
- L115 `test_a_cycle_is_left_alone_rather_than_followed_forever(self)` (method) — Following A→B→A would spin; the merchant's own value is returned
- L123 `ValidationTests` (class)
- L124 `setUp(self)` (method)
- L127 `test_a_self_redirect_is_refused(self)` (method)
- L131 `test_redirecting_to_the_homepage_is_refused_by_default(self)` (method) — Bulk-redirecting dead URLs to / reads as a soft 404 and loses the
- L137 `test_the_homepage_guard_can_be_turned_off(self)` (method)
- L142 `test_a_410_needs_no_target(self)` (method)
- L146 `CacheInvalidationTests` (class)
- L147 `setUp(self)` (method)
- L150 `test_editing_a_rule_takes_effect_immediately(self)` (method) — The resolver reads a cached ruleset. A merchant who edits a rule and
- L159 `test_deleting_a_rule_stops_it_serving(self)` (method)
- L166 `CsvTests` (class)
- L167 `setUp(self)` (method)
- L170 `test_import_round_trips_and_reports_bad_rows(self)` (method) — A 500-row migration from another platform always has a few malformed
- L188 `MiddlewareBehaviourTests` (class)
- L189 `setUp(self)` (method)
- L193 `test_the_query_string_survives_the_redirect(self)` (method) — Dropping ?utm_source breaks campaign attribution for every link that
- L201 `test_an_off_site_destination_is_refused(self)` (method) — `to_path` is staff- AND assistant-writable and went straight into a
- L208 `test_a_410_rule_returns_gone(self)` (method)
- L212 `test_a_language_prefixed_request_matches_an_unprefixed_rule(self)` (method) — LocaleMiddleware leaves /fr/ in path_info, so a rule stored as
- L220 `test_the_dashboard_is_never_redirected(self)` (method)
