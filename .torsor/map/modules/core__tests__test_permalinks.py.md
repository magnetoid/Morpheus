---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/tests/test_permalinks.py

Symbols in `core/tests/test_permalinks.py`.

- L19 `ValidateTemplateTests` (class)
- L20 `test_the_shipped_defaults_are_all_valid(self)` (method)
- L24 `test_a_clean_local_path_is_accepted(self)` (method)
- L28 `test_an_absolute_url_is_refused(self)` (method) — An absolute URL would break hreflang and the sitemap host contract.
- L33 `test_a_query_string_is_refused(self)` (method)
- L37 `test_a_fragment_is_refused(self)` (method)
- L41 `test_a_missing_slug_placeholder_is_refused(self)` (method)
- L45 `test_two_slug_placeholders_are_refused(self)` (method)
- L49 `test_another_placeholder_is_refused(self)` (method)
- L53 `test_a_path_without_trailing_slash_is_refused(self)` (method)
- L57 `test_an_unknown_type_is_refused(self)` (method)
- L62 `ResolverTests` (class)
- L63 `test_a_default_template_produces_the_shipped_path(self)` (method)
- L67 `test_a_merchant_override_wins(self)` (method)
- L71 `test_an_empty_slug_is_refused(self)` (method)
- L76 `test_a_slug_never_escapes_its_segment(self)` (method)
- L80 `test_an_unknown_type_is_refused(self)` (method)
- L85 `test_settings_without_the_override_key_falls_back_to_defaults(self)` (method)
