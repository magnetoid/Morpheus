---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/agents/base.py

Symbols in `core/agents/base.py`.

- L29 `AgentConfigurationError` (class) — Raised when an agent's metadata is invalid at class-definition time.
- L33 `MorpheusAgent` (class) — Base class for every Morpheus agent.
- L74 `__init_subclass__(cls, **kwargs: Any)` (method)
- L95 `get_system_prompt(self, context: dict[str, Any] | None=None)` (method) — Render the system prompt. Override for dynamic prompts.
- L134 `get_tools(self)` (method) — Return the tools this agent can call.
- L163 `on_run_start(self, *, run, context: dict[str, Any])` (method) — Hook called when a run begins; override for custom prep.
- L166 `on_run_end(self, *, run, context: dict[str, Any], result)` (method) — Hook called when a run ends (success or failure).
- L169 `__repr__(self)` (method)
