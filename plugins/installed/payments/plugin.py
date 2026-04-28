from morpheus import Plugin
from morpheus import events
import logging

logger = logging.getLogger('morpheus.plugins.payments')

class PaymentsPlugin(Plugin):
    name = "payments"
    label = "Payments Engine"
    version = "1.0.0"
    description = "Handles payment processing, Stripe integration, and payment intent workflows."
    has_models = True
    requires = ["orders"]

    def ready(self):
        # Register hooks for order payment
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=20)

        # Register GraphQL extensions if we want mutations like `processPayment`
        self.register_graphql_extension('plugins.installed.payments.graphql.mutations')

        try:
            from plugins.installed.payments.gateway import gateway_registry
            from plugins.installed.payments.gateways.manual_gateway import ManualGateway
            from plugins.installed.payments.gateways.stripe_gateway import StripeGateway
            gateway_registry.register(ManualGateway())
            gateway_registry.register(StripeGateway())
        except Exception as e:  # noqa: BLE001
            logger.warning('payments: gateway registration failed: %s', e)

    def on_order_placed(self, order, **kwargs):
        """
        Triggered when an order is placed.
        We can attempt to capture payment if the strategy is synchronous,
        or we can just ensure a payment intent is created.
        """
        logger.info(f"PaymentsPlugin: Order {order.id} placed. Verifying payment status.")
        
    def get_config_schema(self):
        return {
            "type": "object",
            "properties": {
                "stripe_secret_key": {"type": "string", "title": "Stripe Secret Key"},
                "stripe_public_key": {"type": "string", "title": "Stripe Public Key"},
                "stripe_webhook_secret": {"type": "string", "title": "Stripe Webhook Secret"},
                "capture_strategy": {
                    "type": "string", 
                    "enum": ["automatic", "manual"], 
                    "default": "automatic"
                }
            }
        }
