"""agent_mcp plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import Plugin
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
        from morpheus.core import events

        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=20)
        # /agents.md endpoints section — agent_mcp owns the MCP/UCP surfaces, so
        # it advertises them. Disable agent_mcp → the section (and the endpoints)
        # both vanish; the bus skips this handler when the plugin is off.
        self.register_hook(
            events.AGENT_READINESS_SECTIONS, self.on_agent_readiness_sections, priority=10
        )

    def on_order_placed(self, order=None, **kwargs):
        if order is None:
            return
        from plugins.installed.agent_mcp.middleware import stamp_order_with_agent

        stamp_order_with_agent(order)

    def on_agent_readiness_sections(self, value, **kwargs):
        """Contribute the agent-transaction endpoints to /agents.md."""
        from morpheus.core import site_base_url

        base = site_base_url().rstrip('/')
        body = (
            'This store speaks MCP (JSON-RPC 2.0), the Universal Commerce '
            'Protocol, and the Trusted Agent Protocol.\n\n'
            '**MCP servers**\n'
            f'- Storefront (catalog reads, no auth): `POST {base}/mcp/storefront/v1/`\n'
            f'- Cart (no auth): `POST {base}/mcp/cart/v1/`\n'
            f'- Checkout (no auth): `POST {base}/mcp/checkout/v1/`\n'
            f'- Admin (full tool catalog, Bearer auth): `POST {base}/mcp/admin/v1/`\n'
            f'- Manifest: `{base}/mcp/v1/manifest.json` · Health: `{base}/mcp/v1/health/`\n\n'
            '**Discovery manifests**\n'
            f'- Universal Commerce Protocol: `{base}/.well-known/ucp.json`\n'
            f'- Trusted Agent Protocol: `{base}/.well-known/agent.json`\n\n'
            '**Auth**: admin calls need a Bearer token (Dashboard → Developer → '
            'API tokens), scoped per token. Storefront/cart/checkout are public.'
        )
        if isinstance(value, list):
            value.append({'heading': 'Agent commerce endpoints', 'body': body, 'priority': 10})
        return value

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
                hint='Bearer tokens for the MCP server and the API',
            ),
        ]
