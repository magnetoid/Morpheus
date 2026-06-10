---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
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
- L130 `test_severity_clamped(self)` (method)
- L136 `test_missing_source_raises(self)` (method)
- L140 `test_missing_fingerprint_raises(self)` (method)
- L145 `FingerprintForTests` (class)
- L146 `test_deterministic(self)` (method)
- L149 `test_position_sensitive(self)` (method)
- L152 `test_none_treated_as_empty(self)` (method)
- L158 `test_returns_hex_string(self)` (method)
- L164 `IngestJobLifecycleTests` (class)
- L165 `test_start_creates_open_row(self)` (method)
- L173 `test_finish_stamps_status_and_count(self)` (method)
- L181 `test_finish_with_failure(self)` (method)
- L188 `test_finish_truncates_huge_error(self)` (method)
- L195 `IsPathCustomizedTests` (class)
- L196 `test_no_row_returns_false(self)` (method)
- L199 `test_intentional_row_returns_true(self)` (method)
- L207 `test_vendor_specific_returns_true(self)` (method)
- L215 `test_experimental_returns_false(self)` (method)
- L225 `SiSuppressionUniqueConstraintTests` (class)
- L226 `test_two_active_suppressions_for_same_target_blocked(self)` (method)
- L239 `test_expired_suppression_does_not_block_new(self)` (method)
