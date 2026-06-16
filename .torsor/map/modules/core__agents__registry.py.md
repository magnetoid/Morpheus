---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/agents/registry.py

Symbols in `core/agents/registry.py`.

- L19 `AgentRegistry` (class)
- L20 `__init__(self)` (method)
- L28 `register_agent(self, agent: MorpheusAgent, *, plugin: str='')` (method)
- L43 `register_tool(self, tool: Tool, *, plugin: str='')` (method)
- L60 `drop_plugin(self, plugin_name: str)` (method) — Remove every agent + tool contributed by `plugin_name`.
- L71 `get_agent(self, name: str)` (method)
- L74 `get_tool(self, name: str)` (method)
- L77 `all_agents(self)` (method)
- L80 `agents_for_audience(self, audience: str)` (method)
- L83 `platform_tools(self)` (method)
- L86 `tools_for_scopes(self, scopes: list[str])` (method)
- L92 `__repr__(self)` (method)
