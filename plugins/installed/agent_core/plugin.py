"""
agent_core — the platform agent layer plugin.

Wires the kernel `core.agents` module into Django: persistent runs, GraphQL,
streaming chat endpoint, dashboard, and four built-in agents.

Other plugins extend the agent layer through:

    class FooPlugin(Plugin):
        def contribute_agent_tools(self):
            return [my_tool]
        def contribute_agents(self):
            return [MyAgent()]

…which `agent_core` does not need to know about — the registry collects
contributions from every active plugin.
"""
from __future__ import annotations

import logging

from morpheus import Plugin
from morpheus import DashboardPage, SettingsPanel, StorefrontBlock

logger = logging.getLogger('morpheus.agent_core')


class AgentCorePlugin(Plugin):
    # Internal name kept stable — referenced in PluginConfig rows,
    # migrations, scoped permissions. User-facing label + description
    # describe what this plugin actually contributes to Morpheus.
    name = 'agent_core'
    label = 'Linda agent tools + sub-agents'
    version = '1.0.0'
    description = (
        'Tool catalogue Linda calls on — catalog reads + writes, order ops, '
        'inventory, content drafting, analytics. Also: the kernel runtime '
        'shared by sub-agents (Concierge, Merchant Ops, Pricing, Content '
        'Writer). Linda herself lives in core.assistant (not a plugin); '
        'this layer provides her capabilities.'
    )
    has_models = True
    requires = ['catalog', 'orders']

    def ready(self) -> None:
        self.register_graphql_extension('plugins.installed.agent_core.graphql.queries')
        self.register_graphql_extension('plugins.installed.agent_core.graphql.mutations')
        self.register_urls(
            'plugins.installed.agent_core.urls_api',
            prefix='api/',
            namespace='agent_core_api',
        )
        self.register_urls(
            'plugins.installed.agent_core.urls_dashboard',
            prefix='dashboard/agents/',
            namespace='agent_core_dash',
        )
        self._register_beat_schedule()

    def _register_beat_schedule(self) -> None:
        from django.conf import settings
        from celery.schedules import crontab
        schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', None)
        if schedule is None:
            return
        schedule.setdefault(
            'agent_core.background_agents_tick',
            {
                'task': 'plugins.installed.agent_core.tasks.background_agents_tick',
                'schedule': crontab(minute='*'),
            },
        )
        # Daily merchant digest — 07:00 UTC, single MerchantInsight row.
        schedule.setdefault(
            'agent_core.generate_daily_digest',
            {
                'task': 'plugins.installed.agent_core.tasks.generate_daily_digest',
                'schedule': crontab(hour=7, minute=0),
            },
        )
        # Assistant memory decay — 04:00 UTC, drops near-zero relevance rows.
        schedule.setdefault(
            'core_assistant.decay_assistant_memories',
            {
                'task': 'core.assistant.tasks.decay_assistant_memories',
                'schedule': crontab(hour=4, minute=0),
            },
        )

    # ── Contribution surfaces ─────────────────────────────────────────────────

    def contribute_agent_tools(self) -> list:
        from plugins.installed.agent_core.tools import all_builtin_tools
        return all_builtin_tools()

    def contribute_agents(self) -> list:
        from plugins.installed.agent_core.agents import all_builtin_agents
        return all_builtin_agents()

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='global_below_body',
                template='agent_core/blocks/concierge_widget.html',
                priority=80,
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        # All four pages are hidden from the sidebar — they're folded
        # into Linda's domain (the "Linda" parent nav in
        # admin_dashboard/base.html). The DashboardPage rows stay
        # registered so the plugin_page_router resolves the URLs:
        #   /dashboard/apps/agent_core/console/         → Ops console
        #   /dashboard/apps/agent_core/runs/            → Agent runs
        #   /dashboard/apps/agent_core/background/      → Background agents
        #   /dashboard/apps/agent_core/observability/   → Observability
        # The merchant reaches them via the Linda sub-menu, not the
        # apps catalog (which now hides agent_core entirely — it's a
        # SYSTEM_PLUGIN, see admin_dashboard.views_split.apps).
        return [
            DashboardPage(
                label='Ops console',
                slug='console',
                view='plugins.installed.agent_core.views.merchant_ops_chat_view',
                icon='sparkles',
                section='ai',
                order=10,
                nav='hidden',
            ),
            DashboardPage(
                label='Agent runs',
                slug='runs',
                view='plugins.installed.agent_core.views.runs_dashboard_view',
                icon='activity',
                section='ai',
                order=20,
                nav='hidden',
            ),
            DashboardPage(
                label='Background agents',
                slug='background',
                view='plugins.installed.agent_core.views.background_agents_view',
                icon='clock',
                section='ai',
                order=30,
                nav='hidden',
            ),
            DashboardPage(
                label='Observability',
                slug='observability',
                view='plugins.installed.agent_core.views.observability_view',
                icon='gauge',
                section='ai',
                order=40,
                nav='hidden',
            ),
        ]

    # No SettingsPanel — agent_core is a system component, not a
    # user-configurable plugin. Linda's behaviour is tuned via her
    # own dashboard at /dashboard/assistant/ + the AI providers panel
    # (ai_assistant plugin, which carries the actual config knobs:
    # which model, what brand voice, etc.). Surfacing a second
    # "Agents" settings panel here just added noise.
    # The get_config_schema() method below is kept because the kernel
    # reads a few internal flags via plugin.get_config_value(); they
    # just aren't merchant-editable through the dashboard.

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'enable_concierge_widget': {
                    'type': 'boolean', 'default': True,
                    'title': 'Show storefront concierge widget',
                },
                'concierge_greeting': {
                    'type': 'string',
                    'default': 'Hi — I\'m the concierge. What kind of book are you in the mood for?',
                    'title': 'Concierge greeting',
                },
                'merchant_ops_enabled': {
                    'type': 'boolean', 'default': True,
                    'title': 'Enable Merchant Ops console',
                },
            },
        }
