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

# core/tests/test_authz.py

Symbols in `core/tests/test_authz.py`.

- L20 `_plugin()` (function)
- L26 `_set_mode(mode: str)` (function)
- L32 `CapabilityResolutionTests` (class)
- L33 `setUp(self)` (method)
- L43 `test_superuser_always_passes(self)` (method) — The escape hatch: a misconfigured role must never be unrecoverable.
- L47 `test_anonymous_never_passes(self)` (method)
- L53 `test_staff_without_a_role_holds_nothing(self)` (method) — rbac is active and answers: no binding means no capability.
- L57 `test_granting_a_role_grants_its_capabilities(self)` (method)
- L69 `test_falls_back_to_is_staff_when_nothing_answers(self)` (method) — The safety property: with no authority installed, behave as before.
- L87 `EnforcementModeTests` (class)
- L88 `setUp(self)` (method)
- L95 `test_default_is_log_only(self)` (method)
- L100 `test_log_mode_allows_a_failed_check(self)` (method) — The whole point of log mode: report, don't block.
- L105 `test_enforce_mode_denies_a_failed_check(self)` (method)
- L109 `test_off_mode_skips_the_check_entirely(self)` (method)
- L113 `test_a_would_be_denial_is_audited_in_log_mode(self)` (method) — Log mode is only useful if the merchant can read what it caught.
- L124 `test_an_enforced_denial_is_audited(self)` (method)
- L132 `RequireCapabilityDecoratorTests` (class)
- L133 `setUp(self)` (method)
- L149 `_req(self, **headers)` (method)
- L154 `test_log_mode_lets_the_view_run(self)` (method)
- L158 `test_enforce_mode_returns_403(self)` (method)
- L162 `test_enforce_mode_returns_JSON_for_an_ajax_request(self)` (method) — A dashboard fetch endpoint must fail as JSON, or the JS shows a
- L173 `test_the_required_capability_is_introspectable(self)` (method) — Tooling and tests need to see what a view demands without calling it.
- L178 `CapabilityVocabularyTests` (class) — Every capability a view demands must be one a role can actually hold.
- L187 `_vocabulary(self)` (method)
- L192 `_required_capabilities(self)` (method) — {'module:view': 'capability'} for every gated view on disk.
- L207 `test_every_required_capability_is_grantable(self)` (method)
- L220 `test_the_money_paths_are_gated(self)` (method) — Refunds and destructive catalog edits must not be reachable on
