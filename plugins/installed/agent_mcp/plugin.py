"""agent_mcp plugin manifest."""

from __future__ import annotations

import logging

from morpheus import Plugin
from plugins.contributions import DashboardPage

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
        # Stamp the verified agent id onto orders it placed — the manifest
        # advertises order.metadata.agent_id "persisted on checkout"; this is
        # what makes that true (was previously unwired). Disable-safe: the hook
        # bus skips this handler when agent_mcp is off (ADR 0024).
        from morpheus import events

        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=20)

    def on_order_placed(self, order=None, **kwargs):
        if order is None:
            return
        from plugins.installed.agent_mcp.middleware import stamp_order_with_agent

        stamp_order_with_agent(order)

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='API tokens',
                slug='tokens',
                view='plugins.installed.agent_mcp.dashboard.tokens_view',
                icon='key-round',
                section='developer',
                order=20,
                nav='settings',
            ),
        ]
