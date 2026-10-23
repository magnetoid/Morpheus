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

# core/agents/registry.py

Symbols in `core/agents/registry.py`.

- L19 `AgentRegistry` (class)
- L20 `__init__(self)` (method)
- L34 `register_agent(self, agent: MorpheusAgent, *, plugin: str='')` (method)
- L49 `register_tool(self, tool: Tool, *, plugin: str='', replace: bool=False)` (method)
- L96 `drop_plugin(self, plugin_name: str)` (method) — Remove every agent + tool contributed by `plugin_name`.
- L107 `get_agent(self, name: str)` (method)
- L110 `get_tool(self, name: str)` (method)
- L113 `all_agents(self)` (method)
- L116 `agents_for_audience(self, audience: str)` (method)
- L119 `platform_tools(self)` (method)
- L122 `collisions(self)` (method) — Cross-plugin tool-name clashes seen during registration:
- L129 `tools_for_scopes(self, scopes: list[str])` (method)
- L135 `__repr__(self)` (method)
