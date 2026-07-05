"""Analytics plugin — event tracking, funnels, real-time, AI agent stats."""

from __future__ import annotations

from morpheus import DashboardPage, Plugin, SettingsPanel, StorefrontBlock, events


class AnalyticsPlugin(Plugin):
    name = 'analytics'
    label = 'Analytics'
    version = '2.0.0'
    description = (
        'Full-funnel analytics: pageviews, sessions, products, search, cart, '
        'checkout, orders, agent activity. Real-time + daily rollups + funnel '
        'reports + storefront beacon. Agent tools so Merchant Ops can ask.'
    )
    has_models = True

    def ready(self):
        self.register_graphql_extension('plugins.installed.analytics.graphql.queries')
        self.register_celery_tasks('plugins.installed.analytics.tasks')
        self.register_urls(
            'plugins.installed.analytics.urls_api',
            prefix='api/',
            namespace='analytics_api',
        )
        self.register_urls(
            'plugins.installed.analytics.urls_dashboard',
            prefix='dashboard/analytics/v2/',
            namespace='analytics_dash',
        )

        # Hook fan-out — every domain event becomes an analytics event.
        for event in [
            events.ORDER_PLACED,
            events.PAYMENT_CAPTURED,
            events.BEGIN_CHECKOUT,
            events.PRODUCT_VIEWED,
            events.SEARCH_PERFORMED,
            events.CUSTOMER_REGISTERED,
            events.CART_ABANDONED,
        ]:
            self.register_hook(event, self._on_event(event), priority=99)

        # Agent run lifecycle → analytics events.
        try:
            from core.agents import AgentEvents

            for evt in (AgentEvents.RUN_COMPLETED, AgentEvents.RUN_FAILED):
                self.register_hook(evt, self._on_agent_event(evt), priority=99)
        except Exception:  # noqa: BLE001, S110
            pass

        # Beat: roll daily metrics + trim old events.
        self.register_celery_beat(
            'analytics:roll_daily',
            {
                'task': 'analytics.roll_daily',
                'schedule': 60 * 60 * 6,  # every 6 hours
            },
        )
        self.register_celery_beat(
            'analytics:trim_old_events',
            {
                'task': 'analytics.trim_old_events',
                'schedule': 60 * 60 * 24,  # daily
            },
        )

    # ── Hook adapters ────────────────────────────────────────────────────────

    def _on_event(self, event_name: str):
        """Build a hook handler that records an analytics event for `event_name`."""

        def _handler(**kwargs):
            try:
                from plugins.installed.analytics.services import record_event
                from plugins.installed.analytics.tasks import _kind_for

                revenue = None
                product_slug = ''
                customer = None
                if 'order' in kwargs:
                    order = kwargs.get('order')
                    revenue = getattr(order, 'total', None)
                    customer = getattr(order, 'customer', None)
                if 'product' in kwargs:
                    product = kwargs.get('product')
                    product_slug = getattr(product, 'slug', '') or ''
                if 'customer' in kwargs:
                    customer = kwargs.get('customer')

                record_event(
                    name=event_name,
                    kind=_kind_for(event_name),
                    customer=customer,
                    revenue=revenue,
                    product_slug=product_slug,
                    payload={'src': 'hook'},
                )
            except Exception:  # noqa: BLE001, S110
                pass

        return _handler

    def _on_agent_event(self, event_name: str):
        def _handler(**kwargs):
            try:
                from plugins.installed.analytics.services import record_event

                record_event(
                    name=event_name,
                    kind='agent_run',
                    agent_name=str(kwargs.get('agent', ''))[:100],
                    payload={
                        'tokens': int(kwargs.get('tokens', 0) or 0),
                        'error': str(kwargs.get('error', ''))[:500] if kwargs.get('error') else '',
                    },
                )
            except Exception:  # noqa: BLE001, S110
                pass

        return _handler

    # ── Contribution surfaces ────────────────────────────────────────────────

    def contribute_agent_tools(self) -> list:
        from plugins.installed.analytics.agent_tools import (
            analytics_agent_costs_tool,
            analytics_ai_traffic_tool,
            analytics_funnel_tool,
            analytics_realtime_tool,
            analytics_search_trends_tool,
            analytics_summary_tool,
            analytics_top_products_tool,
        )

        return [
            analytics_summary_tool,
            analytics_funnel_tool,
            analytics_search_trends_tool,
            analytics_realtime_tool,
            analytics_agent_costs_tool,
            analytics_ai_traffic_tool,
            analytics_top_products_tool,
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Overview',
                slug='overview',
                view='plugins.installed.analytics.views.overview',
                icon='line-chart',
                section='analytics',
                order=10,
            ),
            DashboardPage(
                label='Real-time',
                slug='realtime',
                view='plugins.installed.analytics.views.realtime',
                icon='radio',
                section='analytics',
                order=20,
            ),
            DashboardPage(
                label='Funnel',
                slug='funnel',
                view='plugins.installed.analytics.views.funnel_view',
                icon='filter',
                section='analytics',
                order=30,
            ),
        ]

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='global_below_body',
                template='analytics/blocks/tracker.html',
                priority=10,
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Analytics',
            description='Event log retention, daily rollups, funnel definitions.',
            schema=self.get_config_schema(),
            category='developer',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'keep_event_days': {
                    'type': 'integer',
                    'default': 90,
                    'minimum': 7,
                    'maximum': 730,
                    'title': 'Days of raw event log to retain',
                },
                'enable_pageview_middleware': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Auto-track storefront pageviews',
                },
                'exclude_staff': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Exclude staff / admins from analytics',
                    'description': (
                        "Don't record the owner's own browsing — they're logged into the "
                        'dashboard, so their storefront visits would skew customer analytics.'
                    ),
                },
                'exclude_logged_in': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Exclude all logged-in customers from analytics',
                    'description': (
                        'Track only anonymous visitors. Off by default — customer funnels '
                        'are usually the point of the data.'
                    ),
                },
            },
        }
