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

# core/assistant/tests/test_ops_proposal.py

Symbols in `core/assistant/tests/test_ops_proposal.py`.

- L22 `_product(**kw)` (function)
- L36 `_change(product, *, field='name', old='Old name', new='New name')` (function)
- L40 `_stage(**kw)` (function)
- L52 `StageProposalTests` (class)
- L53 `test_stage_creates_proposed_row(self)` (method)
- L68 `test_stage_clamps_field_lengths(self)` (method)
- L74 `test_blocked_class_raises_safety_violation(self)` (method)
- L79 `test_stage_records_generic_fk_target(self)` (method)
- L86 `ApproveTests` (class)
- L87 `_proposal(self, **kw)` (method)
- L90 `test_non_staff_fails_closed(self)` (method)
- L101 `test_staff_approve_flips_status(self)` (method)
- L111 `test_approve_expired_flips_to_expired(self)` (method)
- L122 `test_approve_refuses_non_proposed_status(self)` (method)
- L132 `ApplyTests` (class)
- L133 `test_apply_happy_path_mutates_audits_and_flips_status(self)` (method)
- L152 `test_apply_skips_drifted_change_applies_others(self)` (method)
- L173 `test_apply_resolve_failure_reports_error_and_fails_when_nothing_applied(self)` (method)
- L184 `test_apply_partial_success_is_applied_with_errors_reported(self)` (method)
- L200 `test_apply_never_raises_on_terminal_status(self)` (method)
