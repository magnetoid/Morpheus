"""agent_mcp plugin manifest."""
from __future__ import annotations

import logging

from morpheus import Plugin

logger = logging.getLogger('morpheus.agent_mcp')


class AgentMcpPlugin(Plugin):
    name = 'agent_mcp'
    label = 'Agent MCP server'
    version = '0.1.0'
    description = (
        'JSON-RPC server that speaks the Model Context Protocol. Lets '
        'external AI agents (Claude, ChatGPT, Perplexity) discover this '
        'store\'s catalog and tools without per-vendor integrations.'
    )
    has_models = False

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.agent_mcp.urls',
            prefix='mcp/',
            namespace='agent_mcp',
        )
