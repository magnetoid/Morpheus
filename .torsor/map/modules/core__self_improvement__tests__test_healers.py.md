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

# core/self_improvement/tests/test_healers.py

Symbols in `core/self_improvement/tests/test_healers.py`.

- L28 `RegistryTests` (class)
- L29 `test_all_four_phase_2_healers_register(self)` (method)
- L44 `test_analyzer_classes_resolve_to_healers(self)` (method)
- L68 `test_get_healer_returns_correct_subclass(self)` (method)
- L75 `test_get_healer_unknown_returns_none(self)` (method)
- L78 `test_register_rejects_non_healer(self)` (method)
- L86 `MetaDescriptionSummariserTests` (class) — The Phase 2 deterministic summariser is the heart of the healer.
- L89 `setUp(self)` (method)
- L96 `test_short_text_passes_through(self)` (method)
- L101 `test_first_sentence_preferred_when_in_range(self)` (method)
- L110 `test_hard_truncate_falls_back_to_word_boundary(self)` (method)
- L117 `test_empty_text_uses_fallback(self)` (method)
- L121 `test_empty_text_and_fallback(self)` (method)
- L125 `RedirectNormaliserTests` (class)
- L126 `setUp(self)` (method)
- L131 `test_strips_query_string(self)` (method)
- L134 `test_lowercases_slug(self)` (method)
- L137 `test_adds_trailing_slash(self)` (method)
- L140 `test_strips_fragment(self)` (method)
- L143 `test_empty_returns_empty(self)` (method)
- L147 `HealerProposeReturnsExpectedShape` (class) — propose() never raises and always returns the documented shape
- L151 `test_alt_text_empty_recommendation(self)` (method)
- L160 `test_meta_description_empty(self)` (method)
- L170 `test_redirect_empty(self)` (method)
- L178 `test_synonym_empty(self)` (method)
- L187 `SafeToApplyTests` (class) — The safety gate is the last line before a write — exercise it.
- L190 `test_customization_unsafe_blocks_all(self)` (method)
- L198 `test_no_targets_blocks(self)` (method)
- L207 `HealResultDataclass` (class)
- L208 `test_ok_default_empty_details(self)` (method)
- L213 `test_failure_carries_error(self)` (method)
- L219 `RunOneOrchestrationTests` (class) — End-to-end: run_one() drives a Healer through the phases and
- L223 `setUp(self)` (method)
- L239 `test_run_one_blocks_on_class_blocklist(self)` (method) — A class in CLASS_BLOCKLIST gets rejected at the gate.
- L258 `test_run_one_blocks_when_no_healer_registered(self)` (method)
- L269 `test_run_one_seo_gap_arbitrates_candidates_instead_of_no_healer(self)` (method)
- L289 `test_run_one_happy_path_with_stub_healer(self)` (method)
- L325 `test_auto_applied_success_lands_in_terminal_applied(self)` (method) — Regression (July 2026 audit): a successful autonomous run left the
- L363 `test_run_one_rolls_back_when_verify_fails(self)` (method)
- L401 `_StubRec` (class) — Minimal stand-in for SiRecommendation in pure unit tests.
- L404 `__init__(self, *, evidence_signal_ids=None, is_customization_safe=True)` (method)
