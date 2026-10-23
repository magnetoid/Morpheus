---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/ai_assistant/services/intent.py

Symbols in `plugins/installed/ai_assistant/services/intent.py`.

- L32 `IntentTransitionError` (class) — Raised when a state transition is invalid for the current intent state.
- L36 `BudgetExceeded` (class) — Raised when an intent's cost would exceed the agent's budget cap.
- L40 `CapabilityDenied` (class) — Raised when the agent lacks the capability required for this kind of intent.
- L57 `IntentResult` (class)
- L64 `_enforce_intent_engine_enabled()` (function) — The intent engine is gated by the `enable_intent_engine` flag
- L81 `_enforce_capabilities(agent, kind: str)` (function)
- L89 `_enforce_budget(agent, estimated_cost)` (function)
- L100 `propose(*, agent, kind: str, summary: str='', payload: dict[str, Any] | None=None, estimated_cost: Money | None=None, customer=None, channel=None, correlation_id: str='', expires_in_seconds: int | None=600)` (function) — Create a new intent in the `proposed` state.
- L149 `_transition(intent, *, target: str, actor: str='system', note: str='', metadata: dict[str, Any] | None=None)` (function)
- L182 `authorize(intent, *, actor: str='customer', note: str='')` (function) — Customer or merchant approves an intent for execution.
- L195 `reject(intent, *, actor: str='customer', reason: str='')` (function)
- L201 `begin_execute(intent)` (function)
- L206 `complete(intent, *, result: dict[str, Any] | None=None, actual_cost: Money | None=None)` (function) — Mark an executing intent as completed, charge the agent budget, sign the
- L247 `fail(intent, *, error: str, metadata: dict[str, Any] | None=None)` (function)
- L255 `models_F_add(field: str, amount)` (function) — Wrap an F() expression that adds amount to a numeric field, COALESCEing nulls.
