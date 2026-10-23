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

# core/self_improvement/tests/test_services.py

Symbols in `core/self_improvement/tests/test_services.py`.

- L34 `EmitSignalTests` (class)
- L35 `test_creates_row_on_first_call(self)` (method)
- L49 `test_dedupes_identical_fingerprint(self)` (method)
- L57 `test_dedup_bumps_max_severity(self)` (method)
- L64 `test_dedup_merges_payload_non_destructively(self)` (method)
- L78 `test_different_fingerprints_create_separate_rows(self)` (method)
- L84 `test_different_sources_dont_collapse(self)` (method)
- L89 `test_old_signal_outside_window_creates_new_row(self)` (method)
- L101 `test_suppression_silences_signal(self)` (method)
- L111 `test_expired_suppression_does_not_silence(self)` (method)
- L121 `test_unrelated_suppression_passes_through(self)` (method)
- L130 `test_classwide_suppression_silences_every_fingerprint(self)` (method) — A blank match_fingerprint suppresses the whole source/class — the
- L143 `test_severity_clamped(self)` (method)
- L149 `test_missing_source_raises(self)` (method)
- L153 `test_missing_fingerprint_raises(self)` (method)
- L158 `AnalyzerDedupTests` (class) — Regression (July 2026 audit): the analyzer created a fresh
- L164 `_cluster(self, fingerprint='fp-abc')` (method)
- L177 `test_same_cluster_is_not_reproposed(self)` (method)
- L193 `test_distinct_fingerprint_still_creates(self)` (method)
- L205 `FingerprintForTests` (class)
- L206 `test_deterministic(self)` (method)
- L209 `test_position_sensitive(self)` (method)
- L212 `test_none_treated_as_empty(self)` (method)
- L218 `test_returns_hex_string(self)` (method)
- L224 `IngestJobLifecycleTests` (class)
- L225 `test_start_creates_open_row(self)` (method)
- L233 `test_finish_stamps_status_and_count(self)` (method)
- L241 `test_finish_with_failure(self)` (method)
- L248 `test_finish_truncates_huge_error(self)` (method)
- L255 `IsPathCustomizedTests` (class)
- L256 `test_no_row_returns_false(self)` (method)
- L259 `test_intentional_row_returns_true(self)` (method)
- L267 `test_vendor_specific_returns_true(self)` (method)
- L275 `test_experimental_returns_false(self)` (method)
- L285 `SiSuppressionUniqueConstraintTests` (class)
- L286 `test_two_active_suppressions_for_same_target_blocked(self)` (method)
- L299 `test_expired_suppression_does_not_block_new(self)` (method)
