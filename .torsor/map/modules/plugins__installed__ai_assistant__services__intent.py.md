---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/ai_assistant/services/intent.py

Symbols in `plugins/installed/ai_assistant/services/intent.py`.

- L31 `IntentTransitionError` (class) — Raised when a state transition is invalid for the current intent state.
- L35 `BudgetExceeded` (class) — Raised when an intent's cost would exceed the agent's budget cap.
- L39 `CapabilityDenied` (class) — Raised when the agent lacks the capability required for this kind of intent.
- L56 `IntentResult` (class)
- L63 `_enforce_capabilities(agent, kind: str)` (function)
- L71 `_enforce_budget(agent, estimated_cost)` (function)
- L82 `propose(*, agent, kind: str, summary: str='', payload: Optional[dict[str, Any]]=None, estimated_cost: Optional[Money]=None, customer=None, channel=None, correlation_id: str='', expires_in_seconds: Optional[int]=600)` (function) — Create a new intent in the `proposed` state.
- L130 `_transition(intent, *, target: str, actor: str='system', note: str='', metadata: Optional[dict[str, Any]]=None)` (function)
- L163 `authorize(intent, *, actor: str='customer', note: str='')` (function) — Customer or merchant approves an intent for execution.
- L174 `reject(intent, *, actor: str='customer', reason: str='')` (function)
- L180 `begin_execute(intent)` (function)
- L185 `complete(intent, *, result: Optional[dict[str, Any]]=None, actual_cost: Optional[Money]=None)` (function) — Mark an executing intent as completed, charge the agent budget, sign the
- L222 `fail(intent, *, error: str, metadata: Optional[dict[str, Any]]=None)` (function)
- L230 `models_F_add(field: str, amount)` (function) — Wrap an F() expression that adds amount to a numeric field, COALESCEing nulls.
