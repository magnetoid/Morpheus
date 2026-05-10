"""agent_mcp plugin manifest."""
from __future__ import annotations

import logging

from morpheus import Plugin

logger = logging.getLogger('morpheus.agent_mcp')


class AgentMcpPlugin(Plugin):
    name = 'agent_mcp'
    label = 'Agent gateway'
    version = '0.2.0'
    description = (
        'Multi-protocol agent gateway. Four Shopify-shaped MCP servers '
        '(storefront / cart / checkout / admin), Universal Commerce '
        'Protocol discovery manifest, and Trusted Agent Protocol / '
        'Mastercard Verifiable Intent middleware for Cloudflare-signed '
        'agent traffic. External AI clients (Claude, ChatGPT, Comet, '
        'Gemini) discover and transact without per-vendor integrations.'
    )
    has_models = False

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.agent_mcp.urls',
            prefix='mcp/',
            namespace='agent_mcp',
        )
        self.register_urls(
            'plugins.installed.agent_mcp.urls_well_known',
            prefix='.well-known/',
            namespace='agent_mcp_well_known',
        )
