---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/assistant/models.py

Symbols in `core/assistant/models.py`.

- L14 `AssistantConversation` (class)
- L25 `AssistantMessage` (class)
- L50 `LindaMemory` (class) — Cross-session memory for Linda. One row per remembered fact.
- L88 `__str__(self)` (method)
- L91 `relevance_score(self, *, half_life_days: float=60.0)` (method) — Exponential temporal decay weighted by source confidence.
- L119 `LearnedSkill` (class) — A skill Linda authored from experience — a named bundle of EXISTING agent
- L149 `__str__(self)` (method)
- L152 `success_rate(self)` (method)
- L155 `to_skill(self)` (method) — Build a runtime ``Skill`` from this row, resolving ``tool_names``
- L172 `CodeProposal` (class) — A piece of code Linda DRAFTED for herself (uplift Phase 4 — self-written
- L210 `__str__(self)` (method)
- L213 `approve(self, user)` (method) — Owner approval — the binding human gate (ADR 0014). Only a superuser
- L228 `mark_applied(self, branch: str)` (method)
