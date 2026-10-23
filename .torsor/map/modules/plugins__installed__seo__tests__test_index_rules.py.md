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

# plugins/installed/seo/tests/test_index_rules.py

Symbols in `plugins/installed/seo/tests/test_index_rules.py`.

- L31 `ParamPolicyTests` (class)
- L32 `setUp(self)` (method)
- L35 `test_an_unlisted_parameter_consolidates_by_default(self)` (method) — A store gains parameters faster than a merchant writes rules for
- L40 `test_consolidate_drops_the_parameter_and_keeps_the_page_indexable(self)` (method)
- L46 `test_a_no_indexed_page_is_its_own_canonical(self)` (method) — The headline fix. Never `noindex` + a canonical naming another URL.
- L54 `test_tracking_is_still_stripped_from_a_no_indexed_page(self)` (method) — Self-canonical means "this page", not "this URL byte for byte" — a
- L61 `test_an_allowlisted_value_is_a_real_page(self)` (method)
- L69 `test_a_value_off_the_allowlist_is_held_back(self)` (method)
- L78 `test_a_wildcard_matches_a_family(self)` (method)
- L82 `test_a_longer_wildcard_wins(self)` (method) — Same first-match-wins precedence as the redirect resolver.
- L89 `test_an_inactive_rule_does_nothing(self)` (method)
- L93 `test_the_canonical_is_ordered_and_de_duplicated(self)` (method) — `?b=2&a=1` and `?a=1&b=2` are one page; publishing two canonicals for
- L101 `test_a_blocked_parameter_is_never_no_indexed(self)` (method) — robots.txt stops the fetch, so the page's own directives are never
- L109 `test_blocked_parameters_become_robots_patterns(self)` (method)
- L122 `ReservedPageParamTests` (class) — `page` takes no rule: pagination has a policy of its own.
- L125 `setUp(self)` (method)
- L128 `test_page_two_survives_into_the_canonical(self)` (method)
- L131 `test_page_one_collapses(self)` (method)
- L134 `test_page_is_dropped_when_the_view_does_not_paginate(self)` (method) — `/shop/?page=999` on a listing that shows everything on one screen is
- L142 `test_a_zero_padded_page_one_is_still_page_one(self)` (method) — A paginator reads `int(value)`, so `?page=01` renders page 1. Compared
- L149 `test_a_page_value_that_is_not_a_number_is_not_a_page(self)` (method)
- L152 `test_a_wildcard_that_would_block_page_emits_no_robots_pattern(self)` (method) — `page*` set to block would put `Disallow: /*?*page` in robots.txt and
- L160 `test_captures_reserved_names_the_spellings_that_reach_page(self)` (method)
- L167 `test_a_rule_cannot_capture_page(self)` (method) — The one thing a merchant must not be able to do by accident is
- L174 `test_a_wildcard_cannot_capture_page_either(self)` (method)
- L179 `CacheInvalidationTests` (class) — A rule that keeps applying after you deleted it is worse than one that
- L183 `setUp(self)` (method)
- L186 `test_creating_a_rule_takes_effect_immediately(self)` (method)
- L191 `test_deleting_a_rule_takes_effect_immediately(self)` (method)
- L198 `LegacySettingsTests` (class) — An upgrading store's existing configuration keeps working.
- L206 `setUp(self)` (method)
- L209 `test_the_old_settings_list_still_no_indexes(self)` (method)
- L213 `test_a_real_rule_overrides_the_old_list(self)` (method)
- L220 `test_editing_the_old_list_takes_effect_immediately(self)` (method) — The list is compiled into the cached ruleset, so its own settings page
- L230 `test_the_old_list_gets_the_self_canonical_treatment_too(self)` (method) — The legacy path used to strip the parameter *and* no-index — the
- L237 `RuleFormTests` (class) — The editor has to refuse what the engine reserves.
- L245 `setUpTestData(cls)` (method)
- L250 `setUp(self)` (method)
- L255 `_post(self, param, policy='block')` (method)
- L260 `test_a_rule_for_page_is_refused(self)` (method)
- L264 `test_a_wildcard_that_would_capture_page_is_refused(self)` (method)
- L270 `test_the_refusal_says_why(self)` (method)
- L274 `test_an_ordinary_wildcard_is_accepted(self)` (method)
- L278 `test_the_recommended_set_is_idempotent(self)` (method)
- L284 `test_no_recommended_rule_is_one_the_form_would_refuse(self)` (method) — A starter set that seeds a rule the editor rejects would be a rule
- L291 `RuleNormalisationTests` (class)
- L292 `test_a_rule_is_normalised_on_save(self)` (method) — Rules arrive from the dashboard, a shell and an import; one stored as
