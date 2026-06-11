import logging

from morpheus import Plugin, events

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
