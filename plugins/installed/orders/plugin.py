from __future__ import annotations

import logging

from morpheus import events
from morpheus import Plugin, SettingsPanel

logger = logging.getLogger('morpheus.orders')


class OrdersPlugin(Plugin):
    name = 'orders'
    label = 'Orders'
    version = '1.0.0'
    description = 'Cart, order lifecycle, fulfillment, refunds, transactional email.'
    has_models = True
    requires = ['catalog', 'customers']

    def ready(self) -> None:
        self.register_graphql_extension('plugins.installed.orders.graphql.queries')
        self.register_graphql_extension('plugins.installed.orders.graphql.mutations')
        self.register_hook('payment.captured', self.on_payment_captured, priority=10)
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=15)
        from plugins.installed.orders import signals  # noqa: F401 — register signals on import

    def get_config_schema(self):
        return {
            "type": "object",
            "properties": {
                "skip_shipping_for_digital_carts": {
                    "type": "boolean",
                    "default": True,
                    "title": "Skip shipping step for digital/virtual carts",
                    "description": (
                        "When every cart item is flagged "
                        "requires_shipping=False (digital downloads, "
                        "virtual services, gift cards), the checkout "
                        "flow skips the shipping-address form and "
                        "shipping-method picker. Customer only enters "
                        "their email."
                    ),
                },
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Checkout & cart',
            description='Tweaks to the cart + checkout flow. Defaults are sensible for new stores.',
            schema=self.get_config_schema(),
            category='general',
        )

    def on_payment_captured(self, payment, **kwargs):
        from plugins.installed.orders.services import OrderService
        OrderService.confirm_order(payment.order)

    def on_order_placed(self, order, **kwargs):
        """Send the customer their order-confirmation email."""
        try:
            from plugins.installed.orders.email import send_order_confirmation
            send_order_confirmation(order)
        except Exception as e:  # noqa: BLE001 — email never blocks order placement
            logger.warning('orders: confirmation email failed for %s: %s', getattr(order, 'order_number', '?'), e, exc_info=True)

    def contribute_agent_tools(self) -> list:
        from plugins.installed.orders.agent_tools import (
            approve_return_tool, list_returns_tool, refund_order_tool,
        )
        return [refund_order_tool, list_returns_tool, approve_return_tool]
