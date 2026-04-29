from morpheus import Plugin, SettingsPanel, events
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
        # Refunds: when the dashboard records a Refund row it fires this
        # event so the gateway can actually return the money.
        self.register_hook('refund.requested', self.on_refund_requested, priority=20)

        # Register GraphQL extensions if we want mutations like `processPayment`
        self.register_graphql_extension('plugins.installed.payments.graphql.mutations')

        # Mount /payments/webhooks/stripe/ for Stripe to POST events to.
        self.register_urls('plugins.installed.payments.urls', prefix='payments/')

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

    def on_refund_requested(self, refund, **kwargs):
        """Drive the Stripe-side refund when the dashboard records a Refund.

        Looks up the most recent successful PaymentTransaction on the order
        and asks the registered StripeGateway to issue the refund. On
        success, marks ``Refund.is_processed=True``. Failures are logged
        and a staff-visible note is appended.
        """
        from django.utils import timezone
        from plugins.installed.payments.gateway import gateway_registry
        from plugins.installed.payments.models import PaymentTransaction

        order = refund.order
        tx = (
            PaymentTransaction.objects
            .filter(order=order, provider='stripe', status=PaymentTransaction.Status.SUCCEEDED)
            .order_by('-id').first()
        )
        if tx is None:
            logger.info(
                'refund: no successful Stripe transaction on order %s — leaving '
                'refund #%s as manual/pending.', order.order_number, refund.id,
            )
            return

        gateway = gateway_registry.get('stripe') if hasattr(gateway_registry, 'get') else None
        if gateway is None:
            # Iterate registered gateways (older registry shape).
            for g in getattr(gateway_registry, 'all', lambda: [])():
                if getattr(g, 'slug', None) == 'stripe':
                    gateway = g
                    break
        if gateway is None:
            logger.warning('refund: stripe gateway not registered.')
            return

        result = gateway.refund(transaction=tx, amount=refund.amount)
        if result.get('success'):
            refund.is_processed = True
            refund.processed_at = timezone.now()
            refund.save(update_fields=['is_processed', 'processed_at'])
            order.log_event('REFUND_GATEWAY_OK', message=f'{refund.amount}')
        else:
            order.log_event(
                'REFUND_GATEWAY_FAILED',
                message=str(result.get('error', ''))[:240],
            )
        
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
                    "default": "automatic",
                    "title": "Capture strategy",
                },
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Stripe',
            description='Card payments + webhooks. Set keys then register the webhook URL in Stripe.',
            schema=self.get_config_schema(),
            category='payments',
        )
