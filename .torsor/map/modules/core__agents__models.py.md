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

# core/agents/models.py

Symbols in `core/agents/models.py`.

- L26 `AgentRun` (class) — One invocation of an agent.
- L83 `__str__(self)` (method)
- L87 `total_tokens(self)` (method)
- L91 `estimated_cost_usd(self)` (method) — Approximate USD cost of this run (dashboard display, not billing).
- L98 `AgentStep` (class) — One step in a run's trace — mirror of `core.agents.trace.TraceStep`.
- L128 `__str__(self)` (method)
- L132 `AgentApprovalRequest` (class) — Pending approval gate for a tool that requires human sign-off.
- L166 `__str__(self)` (method)
- L170 `ModelUsageDay` (class) — Tokens one model spent today outside the agent runtime's own calls.
- L190 `__str__(self)` (method)
