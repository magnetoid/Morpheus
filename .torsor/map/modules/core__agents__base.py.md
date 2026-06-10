---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:48'
updated: '2026-06-10T20:08:48'
---

# core/agents/base.py

Symbols in `core/agents/base.py`.

- L28 `AgentConfigurationError` (class) — Raised when an agent's metadata is invalid at class-definition time.
- L32 `MorpheusAgent` (class) — Base class for every Morpheus agent.
- L73 `__init_subclass__(cls, **kwargs: Any)` (method)
- L94 `get_system_prompt(self, context: dict[str, Any] | None=None)` (method) — Render the system prompt. Override for dynamic prompts.
- L130 `get_tools(self)` (method) — Return the tools this agent can call.
- L159 `on_run_start(self, *, run, context: dict[str, Any])` (method) — Hook called when a run begins; override for custom prep.
- L162 `on_run_end(self, *, run, context: dict[str, Any], result)` (method) — Hook called when a run ends (success or failure).
- L165 `__repr__(self)` (method)
