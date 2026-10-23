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

# core/agents/tests/test_fallback_budget.py

Symbols in `core/agents/tests/test_fallback_budget.py`.

- L29 `_RecordingProvider` (class) — A provider that records how many times it was called and returns a
- L33 `__init__(self, name: str, response: LLMResponse)` (method)
- L39 `respond(self, **_kw)` (method)
- L44 `FallbackBudgetTests` (class)
- L45 `test_primary_always_runs_and_returns_when_healthy(self)` (method)
- L58 `test_secondary_skipped_when_budget_exhausted(self)` (method)
- L80 `test_secondary_raising_on_call_would_prove_it_was_never_started(self)` (method)
