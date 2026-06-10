---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:00'
updated: '2026-06-09T21:57:00'
---

# core/agents/policies.py

Symbols in `core/agents/policies.py`.

- L13 `AgentPolicyError` (class) — Raised when an agent action violates platform policy.
- L17 `ScopeDenied` (class) — Raised when the caller lacks one or more required scopes.
- L21 `BudgetExceeded` (class) — Raised when an agent's run would exceed its budget cap.
- L25 `enforce_policy(*, scopes: list[str], required: list[str])` (function) — Assert that `scopes` satisfies all entries in `required`.
- L36 `enforce_budget(*, spent: Decimal | float | int, cap: Decimal | float | int | None)` (function)
