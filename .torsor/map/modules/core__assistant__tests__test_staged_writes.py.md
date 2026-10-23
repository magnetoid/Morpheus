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

# core/assistant/tests/test_staged_writes.py

Symbols in `core/assistant/tests/test_staged_writes.py`.

- L26 `_product(**kw)` (function)
- L40 `_order(**kw)` (function)
- L52 `StagedProductToolTests` (class)
- L53 `test_staged_status_change_creates_proposal_and_does_not_mutate(self)` (method)
- L80 `test_staged_context_source_and_agent_run_flow_through(self)` (method)
- L94 `test_unstaged_behavior_unchanged(self)` (method)
- L110 `test_blocked_class_price_change_returns_error_no_proposal(self)` (method)
- L123 `test_staged_proposal_applies_end_to_end(self)` (method)
- L139 `StagedOrderToolTests` (class)
- L140 `test_staged_status_change(self)` (method)
- L163 `test_staged_cancel_uses_reason_as_summary(self)` (method)
- L178 `test_staged_add_note_refuses_without_notes_field(self)` (method)
- L192 `UnstagedOrderToolTests` (class) — The direct (confirmed=True) apply path goes through the order FSM.
- L200 `test_confirmed_update_status_transitions_and_logs_event(self)` (method)
- L214 `test_illegal_transition_raises_toolerror(self)` (method)
- L224 `test_unsupported_status_raises_toolerror(self)` (method)
- L233 `test_confirmed_cancel_applies_and_sets_cancelled_at(self)` (method)
- L250 `StagedCustomerToolTests` (class)
- L251 `test_staged_add_note(self)` (method)
- L268 `StagedMetafieldToolTests` (class)
- L269 `test_staged_set_updates_existing_row(self)` (method)
- L301 `test_staged_set_of_new_key_refuses(self)` (method)
- L317 `test_staged_delete_refuses(self)` (method)
- L339 `StagedCmsToolTests` (class)
- L340 `test_staged_publish_and_unpublish(self)` (method)
