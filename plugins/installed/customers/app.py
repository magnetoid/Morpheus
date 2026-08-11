import logging

from morpheus.app import Plugin
from morpheus.core import events

logger = logging.getLogger('morpheus.customers')


class CustomersPlugin(Plugin):
    name = 'customers'
    label = 'Customers'
    version = '1.0.0'
    description = 'Customer accounts, addresses, and authentication.'
    has_models = True

    def ready(self):
        self.register_graphql_extension('plugins.installed.customers.graphql.queries')
        self.register_graphql_extension('plugins.installed.customers.graphql.mutations')
        # Allauth's signup signal is bridged onto the hook bus in signals.py —
        # importing it here registers the `@receiver(user_signed_up)`.
        from plugins.installed.customers import signals  # noqa

        self.register_hook(events.ORDER_PAID, self.on_order_paid, priority=20)

        # Nightly RFM re-scoring (04:30 — before the dynamics 3:30/4:00 jobs have
        # long finished and orders have settled). Fires CUSTOMER_SEGMENT_CHANGED.
        from celery.schedules import crontab  # noqa: PLC0415

        self.register_celery_tasks('plugins.installed.customers.tasks')
        self.register_celery_beat(
            'customers:recompute_rfm',
            {'task': 'customers.recompute_rfm', 'schedule': crontab(hour=4, minute=30)},
        )

    def contribute_dashboard_pages(self) -> list:
        from morpheus.app import DashboardPage  # noqa: PLC0415

        return [
            DashboardPage(
                label='Segments',
                slug='segments',
                view='plugins.installed.customers.views_rfm.segments_dashboard',
                icon='users',
                section='customers',
                order=80,
            ),
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.customers.agent_tools import (  # noqa: PLC0415
            customers_get_tool,
            customers_search_tool,
        )

        return [customers_search_tool, customers_get_tool]

    def on_order_paid(self, order, **kwargs):
        from plugins.installed.customers.services import update_cdp_metrics

        try:
            update_cdp_metrics(order)
        except Exception as e:  # noqa: BLE001 — CDP failure must not break checkout
            logger.warning(
                'customers: CDP update failed for order %s: %s',
                getattr(order, 'pk', '?'),
                e,
                exc_info=True,
            )
