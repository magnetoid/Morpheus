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

# core/assistant/tests/test_enforcement.py

Symbols in `core/assistant/tests/test_enforcement.py`.

- L28 `_tool(name, *, scopes=None, requires_approval=False, supports_staging=False)` (function)
- L40 `_gate(tool, *, args=None, context=None, conversation_key='k', human_message='', **kw)` (function)
- L53 `ScopeGateTests` (class)
- L54 `test_tool_within_profile_allowed(self)` (method)
- L57 `test_tool_outside_profile_denied(self)` (method)
- L63 `test_consent_override_gates_a_tool_without_its_own_flag(self)` (method)
- L68 `test_unscoped_tool_allowed(self)` (method)
- L72 `BudgetAndDeadlineTests` (class)
- L73 `test_budget_exceeded_blocks(self)` (method)
- L77 `test_zero_budget_is_unlimited(self)` (method)
- L81 `test_past_deadline_blocks(self)` (method)
- L87 `HumanConsentGateTests` (class) — The core fix: consent is human-attested and kernel-verified.
- L90 `setUp(self)` (method)
- L95 `_gate(self, *, human_message, args=None, context=None)` (method)
- L104 `test_llm_supplied_confirmed_flag_is_not_consent(self)` (method)
- L110 `test_human_yes_after_proposal_allows_once(self)` (method)
- L117 `test_consent_is_bound_to_exact_arguments(self)` (method)
- L123 `test_negation_wins_over_affirmation(self)` (method)
- L127 `test_staging_tool_exempt_only_in_staged_mode(self)` (method)
- L139 `test_non_staging_tool_still_gated_under_staged_context(self)` (method)
- L146 `ConsentOrderingTests` (class) — Consent is spent only by a human message sent AFTER the proposal.
- L154 `setUp(self)` (method)
- L158 `test_message_older_than_the_proposal_is_not_consent(self)` (method)
- L163 `test_message_after_the_proposal_is_consent(self)` (method)
- L168 `test_entry_written_before_proposal_times_existed_fails_closed(self)` (method)
- L177 `test_gate_passes_the_message_time_through(self)` (method)
- L197 `WriteAuditTests` (class) — Which calls count as writes for `assistant.tool_write`.
- L200 `test_write_scopes_and_approval_tools_are_writes(self)` (method)
- L207 `test_reads_are_not(self)` (method)
- L212 `AffirmativeParsingTests` (class)
- L213 `test_affirmatives(self)` (method)
- L217 `test_non_affirmatives(self)` (method)
- L221 `test_negation_beats_affirmation(self)` (method)
