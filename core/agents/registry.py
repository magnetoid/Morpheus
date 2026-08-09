"""
Agent registry — discovers agents and tools contributed by plugins.

Populated by `plugins.registry.PluginRegistry._collect_contributions` after
each plugin's `ready()`. The registry is process-wide and read-only at
runtime (it's only mutated during plugin activation/deactivation).
"""

from __future__ import annotations

import logging

from core.agents.base import MorpheusAgent
from core.agents.tools import Tool

logger = logging.getLogger('morpheus.agents.registry')


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, MorpheusAgent] = {}
        self._tools: dict[str, Tool] = {}
        self._tool_owners: dict[str, str] = {}  # tool_name -> plugin_name
        self._agent_owners: dict[str, str] = {}  # agent_name -> plugin_name
        # (tool_name, prior_owner, new_owner) for every CROSS-plugin name clash
        # seen during registration. Two plugins claiming one name means the
        # winner is decided by plugin load order — and the MCP-served version
        # becomes non-deterministic — so we surface these (warning + this list,
        # asserted by a CI test) instead of silently overwriting.
        self._collisions: list[tuple[str, str, str]] = []

    # ── Registration (called by PluginRegistry) ────────────────────────────────

    def register_agent(self, agent: MorpheusAgent, *, plugin: str = '') -> None:
        if not agent.name:
            logger.warning('agent_registry: refusing nameless agent from plugin=%s', plugin)
            return
        if agent.name in self._agents:
            logger.debug(
                'agent_registry: replacing agent %s (was from %s, now %s)',
                agent.name,
                self._agent_owners.get(agent.name, '?'),
                plugin,
            )
        self._agents[agent.name] = agent
        if plugin:
            self._agent_owners[agent.name] = plugin

    def register_tool(self, tool: Tool, *, plugin: str = '') -> None:
        if not tool.name:
            logger.warning('agent_registry: refusing nameless tool from plugin=%s', plugin)
            return
        if tool.name in self._tools:
            prior_owner = self._tool_owners.get(tool.name, '')
            if prior_owner and plugin and prior_owner != plugin:
                # A different plugin already owns this name — a true collision.
                # Last-writer-wins by load order makes the served tool
                # non-deterministic; one-concept-one-owner is violated.
                logger.warning(
                    'agent_registry: tool name COLLISION %r — %s overwriting %s '
                    '(winner depends on plugin load order; rename one)',
                    tool.name,
                    plugin,
                    prior_owner,
                )
                self._collisions.append((tool.name, prior_owner, plugin))
            else:
                # Same plugin re-registering (e.g. reactivation) — benign.
                logger.debug(
                    'agent_registry: replacing tool %s (was from %s, now %s)',
                    tool.name,
                    prior_owner or '?',
                    plugin,
                )
        if plugin and not tool.plugin:
            tool.plugin = plugin
        self._tools[tool.name] = tool
        if plugin:
            self._tool_owners[tool.name] = plugin

    def drop_plugin(self, plugin_name: str) -> None:
        """Remove every agent + tool contributed by `plugin_name`."""
        for agent_name in [n for n, p in self._agent_owners.items() if p == plugin_name]:
            self._agents.pop(agent_name, None)
            self._agent_owners.pop(agent_name, None)
        for tool_name in [n for n, p in self._tool_owners.items() if p == plugin_name]:
            self._tools.pop(tool_name, None)
            self._tool_owners.pop(tool_name, None)

    # ── Read accessors ─────────────────────────────────────────────────────────

    def get_agent(self, name: str) -> MorpheusAgent | None:
        return self._agents.get(name)

    def get_tool(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all_agents(self) -> list[MorpheusAgent]:
        return list(self._agents.values())

    def agents_for_audience(self, audience: str) -> list[MorpheusAgent]:
        return [a for a in self._agents.values() if a.audience in (audience, 'any')]

    def platform_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def collisions(self) -> list[tuple[str, str, str]]:
        """Cross-plugin tool-name clashes seen during registration:
        (tool_name, prior_owner, new_owner). Asserted against a known baseline
        by core/agents/tests/test_registry_collisions.py so a NEW collision
        fails CI. Shrinks as the duplicate tool families are consolidated."""
        return list(self._collisions)

    def tools_for_scopes(self, scopes: list[str]) -> list[Tool]:
        scope_set = set(scopes)
        return [
            t for t in self._tools.values() if not t.scopes or set(t.scopes).issubset(scope_set)
        ]

    def __repr__(self) -> str:
        return f'<AgentRegistry: {len(self._agents)} agents, {len(self._tools)} tools>'


agent_registry = AgentRegistry()
