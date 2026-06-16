---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/agents/policies.py

Symbols in `core/agents/policies.py`.

- L14 `AgentPolicyError` (class) — Raised when an agent action violates platform policy.
- L18 `ScopeDenied` (class) — Raised when the caller lacks one or more required scopes.
- L22 `BudgetExceeded` (class) — Raised when an agent's run would exceed its budget cap.
- L26 `enforce_policy(*, scopes: list[str], required: list[str])` (function) — Assert that `scopes` satisfies all entries in `required`.
- L37 `enforce_budget(*, spent: Decimal | float | int, cap: Decimal | float | int | None)` (function)
