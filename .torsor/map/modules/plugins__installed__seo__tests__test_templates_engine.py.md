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

# plugins/installed/seo/tests/test_templates_engine.py

Symbols in `plugins/installed/seo/tests/test_templates_engine.py`.

- L18 `_product(name='The Last Archive', slug='the-last-archive', category=None)` (function)
- L29 `GrammarTests` (class)
- L30 `setUp(self)` (method)
- L33 `test_plain_token(self)` (method)
- L38 `test_fallback_chain_and_literal(self)` (method)
- L45 `test_filters(self)` (method)
- L51 `test_bracket_block_vanishes_when_empty(self)` (method)
- L56 `test_template_with_no_resolving_token_declines(self)` (method) — Boilerplate with only dead tokens must return '', not publish
- L61 `test_graphql_dict_object(self)` (method) — The PDP renders a GraphQL dict — the kind that matters most must
- L67 `test_deferred_money_fields_do_not_kill_the_render(self)` (method) — The PDP loads products with .only(), and a deferred djmoney column
- L80 `ResolutionTests` (class)
- L81 `setUp(self)` (method)
- L86 `_title(self)` (method)
- L89 `test_empty_only_fills_the_gap(self)` (method)
- L93 `test_empty_only_loses_to_a_typed_value(self)` (method) — The P1 lesson holds: a merchant's own meta title beats the pattern.
- L100 `test_all_mode_deliberately_overrides(self)` (method)
- L108 `test_scoped_rule_beats_global(self)` (method)
- L115 `test_declining_template_falls_through_to_the_guess(self)` (method) — autofill mints a SeoMeta guess (the product name) on creation; a
- L122 `test_no_page_kind_means_no_template_layer(self)` (method) — Panels and previews resolve without kind — patterns must not leak
- L130 `test_save_invalidates_the_compiled_cache(self)` (method)
- L138 `test_inactive_rule_is_ignored(self)` (method)
- L146 `DashboardPageTests` (class)
- L149 `_staff(self)` (method)
- L159 `test_anonymous_is_redirected(self)` (method)
- L162 `test_staff_can_create_and_preview(self)` (method)
- L185 `test_pattern_without_a_token_is_rejected(self)` (method)
