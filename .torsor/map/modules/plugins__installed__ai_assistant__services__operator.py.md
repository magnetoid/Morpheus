---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/ai_assistant/services/operator.py

Symbols in `plugins/installed/ai_assistant/services/operator.py`.

- L20 `AgentOperator` (class) — Compatibility wrapper that hands an objective to the generic Worker.
- L23 `__init__(self, provider: str='')` (method)
- L26 `run_workflow(self, objective: str)` (method) — Run an objective through the generic Worker.
- L52 `execute_tool(self, tool_name: str, kwargs: dict[str, Any])` (method) — Direct tool invocation (no LLM). Useful for tests + scripted automations.
