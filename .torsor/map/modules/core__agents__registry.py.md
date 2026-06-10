---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:48'
updated: '2026-06-10T20:08:48'
---

# core/agents/registry.py

Symbols in `core/agents/registry.py`.

- L19 `AgentRegistry` (class)
- L21 `__init__(self)` (method)
- L29 `register_agent(self, agent: MorpheusAgent, *, plugin: str='')` (method)
- L40 `register_tool(self, tool: Tool, *, plugin: str='')` (method)
- L53 `drop_plugin(self, plugin_name: str)` (method) — Remove every agent + tool contributed by `plugin_name`.
- L64 `get_agent(self, name: str)` (method)
- L67 `get_tool(self, name: str)` (method)
- L70 `all_agents(self)` (method)
- L73 `agents_for_audience(self, audience: str)` (method)
- L76 `platform_tools(self)` (method)
- L79 `tools_for_scopes(self, scopes: list[str])` (method)
- L86 `__repr__(self)` (method)
