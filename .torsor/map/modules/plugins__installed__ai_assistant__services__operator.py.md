---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/ai_assistant/services/operator.py

Symbols in `plugins/installed/ai_assistant/services/operator.py`.

- L19 `AgentOperator` (class) — Compatibility wrapper that hands an objective to the generic Worker.
- L22 `__init__(self, provider: str='')` (method)
- L25 `run_workflow(self, objective: str)` (method) — Run an objective through the generic Worker.
- L51 `execute_tool(self, tool_name: str, kwargs: dict[str, Any])` (method) — Direct tool invocation (no LLM). Useful for tests + scripted automations.
