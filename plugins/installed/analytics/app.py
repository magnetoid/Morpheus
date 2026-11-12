"""Analytics plugin — event tracking, funnels, real-time, AI agent stats."""

from __future__ import annotations

from morpheus.app import DashboardCard, DashboardPage, Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events

#: Events a crawler can cause by browsing; the rest are orders and accounts.
_BROWSING = (events.PRODUCT_VIEWED, events.SEARCH_PERFORMED, events.ADD_TO_CART)
#: The name an event is stored under, where the funnels and rollups use another.
_NAMES = {events.ADD_TO_CART: 'cart.add'}


def _payload(kwargs: dict) -> dict:
    """What an event keeps beyond its columns: the order it is about, so a
    report can read the order's net amount, and a search's result count, so a
    search that found nothing can be told from one that did."""
    payload = {'src': 'hook'}
    order_pk = getattr(kwargs.get('order'), 'pk', None)
    if order_pk:
        payload['order'] = str(order_pk)
    try:
        if kwargs.get('result_count') is not None:
            payload['results'] = int(kwargs['result_count'])
    except (TypeError, ValueError):
        pass
    return payload


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
    #: Revenue in every report is the orders app's sales figure (orders.reports).
    requires = ['orders']

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
            events.ADD_TO_CART,
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

        # Beat: roll today's and yesterday's metrics, trim old events and visitors.
        self.register_celery_beat(
            'analytics:roll_daily',
            {
                'task': 'analytics.roll_daily',
                'schedule': 60 * 60,  # hourly, so today's numbers are an hour old at most
            },
        )
        self.register_celery_beat(
            'analytics:trim_old_visitors',
            {'task': 'analytics.trim_old_visitors', 'schedule': 60 * 60 * 24},
        )
        self.register_celery_beat(
            'analytics:trim_old_events',
            {
                'task': 'analytics.trim_old_events',
                'schedule': 60 * 60 * 24,  # daily
            },
        )
        self.register_celery_beat(
            'analytics:detect_anomalies',
            {
                'task': 'analytics.detect_anomalies',
                'schedule': 60 * 60 * 24,  # daily, after roll_daily has run
            },
        )
        # Attribution: pull channel ad spend, then reconstruct journeys + attribute.
        self.register_celery_beat(
            'analytics:collect_ad_spend',
            {'task': 'analytics.collect_ad_spend', 'schedule': 60 * 60 * 24},  # daily
        )
        self.register_celery_beat(
            'analytics:attribute_revenue',
            {'task': 'analytics.attribute_revenue', 'schedule': 60 * 60 * 24},  # daily, after spend
        )

        # Dashboard-home presence: KPI tiles + anomaly activity — via the
        # filter bus, so a disabled plugin's tiles simply never render.
        from plugins.installed.analytics import dashboard  # noqa: PLC0415

        self.register_hook(events.DASHBOARD_KPIS, dashboard.on_dashboard_kpis, priority=30)
        self.register_hook(events.ACTIVITY_FEED, dashboard.on_activity_feed, priority=50)

    # ── Hook adapters ────────────────────────────────────────────────────────

    def _on_event(self, event_name: str):
        """Build a hook handler that records an analytics event for `event_name`."""

        def _handler(**kwargs):
            try:
                from plugins.installed.analytics import services
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

                # Server-side storefront fires pass request= so the event
                # joins the visitor's session (funnels group by session_id).
                request = kwargs.get('request')
                session = None
                order = kwargs.get('order')
                if event_name == events.ORDER_PLACED and request is None:
                    # Checkout fires it without the request; the shopper's own
                    # request is the one being served. A later event (a webhook
                    # capturing the payment) runs on someone else's request.
                    request = services.shopper_request()
                if request is None and order is not None:
                    session = services.order_session(order)
                # Browsing by a crawler is not a visitor's product view, search
                # or cart. Orders are kept whoever the client is.
                if event_name in _BROWSING and request:
                    from core.utils.crawlers import is_crawler_user_agent  # noqa: PLC0415

                    if is_crawler_user_agent(request.META.get('HTTP_USER_AGENT', '')):
                        return
                evt = record_event(
                    name=_NAMES.get(event_name, event_name),
                    kind=_kind_for(event_name),
                    request=request,
                    session=session,
                    customer=customer,
                    revenue=revenue,
                    product_slug=product_slug,
                    search_query=str(kwargs.get('query') or '')[:200],
                    url=(getattr(request, 'path', '') or '')[:500],
                    payload=_payload(kwargs),
                )
                if event_name == events.ORDER_PLACED and evt is not None and order is not None:
                    services.link_order(order, evt)
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
            analytics_traffic_sources_tool,
        )

        return [
            analytics_summary_tool,
            analytics_funnel_tool,
            analytics_search_trends_tool,
            analytics_realtime_tool,
            analytics_agent_costs_tool,
            analytics_ai_traffic_tool,
            analytics_top_products_tool,
            analytics_traffic_sources_tool,
        ]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Traffic',
                slug='overview',
                view='plugins.installed.analytics.views.overview',
                icon='line-chart',
                section='analytics',
                order=20,
            ),
            DashboardPage(
                label='Sources',
                slug='sources',
                view='plugins.installed.analytics.views.sources_view',
                icon='route',
                section='analytics',
                order=25,
            ),
            DashboardPage(
                label='Search terms',
                slug='search-terms',
                view='plugins.installed.analytics.views.search_terms_view',
                icon='search',
                section='analytics',
                order=26,
            ),
            DashboardPage(
                label='Real-time',
                slug='realtime',
                view='plugins.installed.analytics.views.realtime',
                icon='radio',
                section='analytics',
                order=30,
            ),
            DashboardPage(
                label='Funnel',
                slug='funnel',
                view='plugins.installed.analytics.views.funnel_view',
                icon='filter',
                section='analytics',
                order=40,
            ),
            DashboardPage(
                label='Cohorts',
                slug='cohorts',
                view='plugins.installed.analytics.views.cohort_view',
                icon='users',
                section='analytics',
                order=50,
            ),
            DashboardPage(
                label='Attribution',
                slug='attribution',
                view='plugins.installed.analytics.views_attribution.attribution_view',
                icon='git-merge',
                section='analytics',
                order=60,
            ),
        ]

    def contribute_dashboard_cards(self) -> list:
        return [
            DashboardCard(
                section='analytics',
                title='Where visits came from',
                data='plugins.installed.analytics.cards.sources_card',
                url='/dashboard/apps/analytics/sources/',
                cta='Open sources',
                icon='route',
                order=40,
                capability='analytics.read',
            )
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
            category='channels',
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
                'exclude_staff': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Exclude staff / admins from analytics',
                    'description': (
                        "Don't record the owner's own browsing — they're logged into the "
                        'dashboard, so their storefront visits would skew customer analytics.'
                    ),
                },
                'cookieless_visits': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Count visitors who decline analytics cookies',
                    'description': (
                        'Counts their visits with a key that changes every day and is '
                        'never stored with a customer or an order, so it cannot follow '
                        'anyone. Check with your privacy adviser that audience '
                        'measurement without consent is allowed where you sell.'
                    ),
                },
                'keep_visitor_days': {
                    'type': 'integer',
                    'default': 395,
                    'minimum': 30,
                    'maximum': 730,
                    'title': 'Days to keep a visitor who has not come back',
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
