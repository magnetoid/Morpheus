---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/ai_assistant/services/intent.py

Symbols in `plugins/installed/ai_assistant/services/intent.py`.

- L32 `IntentTransitionError` (class) — Raised when a state transition is invalid for the current intent state.
- L36 `BudgetExceeded` (class) — Raised when an intent's cost would exceed the agent's budget cap.
- L40 `CapabilityDenied` (class) — Raised when the agent lacks the capability required for this kind of intent.
- L57 `IntentResult` (class)
- L64 `_enforce_capabilities(agent, kind: str)` (function)
- L72 `_enforce_budget(agent, estimated_cost)` (function)
- L83 `propose(*, agent, kind: str, summary: str='', payload: dict[str, Any] | None=None, estimated_cost: Money | None=None, customer=None, channel=None, correlation_id: str='', expires_in_seconds: int | None=600)` (function) — Create a new intent in the `proposed` state.
- L131 `_transition(intent, *, target: str, actor: str='system', note: str='', metadata: dict[str, Any] | None=None)` (function)
- L164 `authorize(intent, *, actor: str='customer', note: str='')` (function) — Customer or merchant approves an intent for execution.
- L177 `reject(intent, *, actor: str='customer', reason: str='')` (function)
- L183 `begin_execute(intent)` (function)
- L188 `complete(intent, *, result: dict[str, Any] | None=None, actual_cost: Money | None=None)` (function) — Mark an executing intent as completed, charge the agent budget, sign the
- L229 `fail(intent, *, error: str, metadata: dict[str, Any] | None=None)` (function)
- L237 `models_F_add(field: str, amount)` (function) — Wrap an F() expression that adds amount to a numeric field, COALESCEing nulls.
