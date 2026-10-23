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

# core/agents/approval.py

Symbols in `core/agents/approval.py`.

- L23 `args_fingerprint(tool_name: str, args: dict | None)` (function) — Stable fingerprint of one tool invocation (name + canonical args), so an
- L31 `_ApprovalRegistry` (class)
- L32 `__init__(self)` (method)
- L35 `register(self, resolver: _Resolver)` (method) — Install the DB-backed resolver (idempotent — last wins).
- L39 `reset(self)` (method) — Drop the resolver (tests / plugin disable) → back to fail-closed.
- L43 `check(self, tool_name: str, args: dict, context: dict)` (method) — True only when a resolver affirmatively confirms an approval is on
