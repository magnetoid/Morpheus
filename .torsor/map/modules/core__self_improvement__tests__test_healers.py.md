---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# core/self_improvement/tests/test_healers.py

Symbols in `core/self_improvement/tests/test_healers.py`.

- L28 `RegistryTests` (class)
- L29 `test_all_four_phase_2_healers_register(self)` (method)
- L44 `test_get_healer_returns_correct_subclass(self)` (method)
- L51 `test_get_healer_unknown_returns_none(self)` (method)
- L54 `test_register_rejects_non_healer(self)` (method)
- L62 `MetaDescriptionSummariserTests` (class) — The Phase 2 deterministic summariser is the heart of the healer.
- L65 `setUp(self)` (method)
- L72 `test_short_text_passes_through(self)` (method)
- L77 `test_first_sentence_preferred_when_in_range(self)` (method)
- L86 `test_hard_truncate_falls_back_to_word_boundary(self)` (method)
- L93 `test_empty_text_uses_fallback(self)` (method)
- L97 `test_empty_text_and_fallback(self)` (method)
- L101 `RedirectNormaliserTests` (class)
- L102 `setUp(self)` (method)
- L107 `test_strips_query_string(self)` (method)
- L110 `test_lowercases_slug(self)` (method)
- L113 `test_adds_trailing_slash(self)` (method)
- L116 `test_strips_fragment(self)` (method)
- L119 `test_empty_returns_empty(self)` (method)
- L123 `HealerProposeReturnsExpectedShape` (class) — propose() never raises and always returns the documented shape
- L127 `test_alt_text_empty_recommendation(self)` (method)
- L136 `test_meta_description_empty(self)` (method)
- L146 `test_redirect_empty(self)` (method)
- L154 `test_synonym_empty(self)` (method)
- L163 `SafeToApplyTests` (class) — The safety gate is the last line before a write — exercise it.
- L166 `test_customization_unsafe_blocks_all(self)` (method)
- L174 `test_no_targets_blocks(self)` (method)
- L183 `HealResultDataclass` (class)
- L184 `test_ok_default_empty_details(self)` (method)
- L189 `test_failure_carries_error(self)` (method)
- L195 `RunOneOrchestrationTests` (class) — End-to-end: run_one() drives a Healer through the phases and
- L199 `setUp(self)` (method)
- L215 `test_run_one_blocks_on_class_blocklist(self)` (method) — A class in CLASS_BLOCKLIST gets rejected at the gate.
- L234 `test_run_one_blocks_when_no_healer_registered(self)` (method)
- L245 `test_run_one_happy_path_with_stub_healer(self)` (method)
- L281 `test_run_one_rolls_back_when_verify_fails(self)` (method)
- L319 `_StubRec` (class) — Minimal stand-in for SiRecommendation in pure unit tests.
- L322 `__init__(self, *, evidence_signal_ids=None, is_customization_safe=True)` (method)
