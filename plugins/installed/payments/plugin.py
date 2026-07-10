# ruff: noqa: PLC0415, I001
# Inline imports in ready()/hooks are intentional — gateway + model
# modules must not load before the app registry is ready.
import logging

from morpheus import Plugin, SettingsPanel, events

logger = logging.getLogger('morpheus.plugins.payments')


class PaymentsPlugin(Plugin):
    name = 'payments'
    label = 'Payments Engine'
    version = '1.0.0'
    description = 'Handles payment processing, Stripe integration, and payment intent workflows.'
    has_models = True
    requires = ['orders']

    def ready(self):
        # Register hooks for order payment
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=20)
        # Refunds: when the dashboard records a Refund row it fires this
        # event so the gateway can actually return the money.
        self.register_hook('refund.requested', self.on_refund_requested, priority=20)
        # GDPR slice: contribute this plugin's data to the export/erasure.
        from plugins.installed.payments import gdpr  # noqa: PLC0415

        self.register_hook(events.CUSTOMER_ANONYMISE, gdpr.on_customer_anonymise, priority=70)
        # Checkout payment-method picker — the storefront asks via this filter
        # instead of importing payments.services.routing, so the picker empties
        # on disable.
        self.register_hook(events.CHECKOUT_GATEWAYS, self.on_checkout_gateways, priority=10)

        # Register GraphQL extensions if we want mutations like `processPayment`
        self.register_graphql_extension('plugins.installed.payments.graphql.mutations')

        # Mount /payments/webhooks/stripe/ for Stripe to POST events to.
        self.register_urls('plugins.installed.payments.urls', prefix='payments/')
        # Apple Pay domain verification for the Payment Element wallets.
        self.register_urls(
            'plugins.installed.payments.urls_well_known',
            prefix='.well-known/',
            namespace='payments_well_known',
        )

        try:
            from plugins.installed.payments.gateway import gateway_registry
            from plugins.installed.payments.gateways.manual_gateway import ManualGateway
            from plugins.installed.payments.gateways.paypal_gateway import PayPalGateway
            from plugins.installed.payments.gateways.stripe_gateway import StripeGateway

            gateway_registry.register(ManualGateway())
            gateway_registry.register(StripeGateway())
            gateway_registry.register(PayPalGateway())
        except Exception as e:  # noqa: BLE001
            logger.warning('payments: gateway registration failed: %s', e)

        # Settings → Payments saves land in PluginConfig; enabled_gateways()
        # reads PaymentGatewayConfig — project the paypal toggle across on
        # every panel save (same bridge advanced_payments uses for cod/test).
        try:
            from django.db.models.signals import post_save

            from plugins.models import PluginConfig

            post_save.connect(
                self._on_own_config_saved,
                sender=PluginConfig,
                dispatch_uid='payments-paypal-gateway-sync',
                weak=False,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning('payments: paypal config-sync wiring failed: %s', e)

    @staticmethod
    def _on_own_config_saved(sender, instance, **kwargs):
        if getattr(instance, 'plugin_name', None) == 'payments':
            from plugins.installed.payments.services.paypal import sync_gateway_row

            sync_gateway_row()


    def on_checkout_gateways(self, value, **kwargs):
        """CHECKOUT_GATEWAYS: enabled-gateway dicts for the checkout picker."""
        from plugins.installed.payments.services.routing import picker_gateways  # noqa: PLC0415

        return picker_gateways()

    def on_order_placed(self, order, **kwargs):
        """
        Triggered when an order is placed.
        We can attempt to capture payment if the strategy is synchronous,
        or we can just ensure a payment intent is created.
        """
        logger.info(f'PaymentsPlugin: Order {order.id} placed. Verifying payment status.')

    def on_refund_requested(self, refund, **kwargs):
        """Drive the gateway-side refund when the dashboard records a Refund.

        Routes through the gateway that processed the order
        (``order.payment_gateway``, defaulting to 'stripe' for legacy
        orders + the common path). Looks up the most recent successful
        PaymentTransaction for that provider and asks the registered
        gateway to issue the refund. On success, marks
        ``Refund.is_processed=True``. Failures are logged and a
        staff-visible note is appended. COD/manual orders have no
        transaction, so they no-op here (reconciled offline).
        """
        from django.utils import timezone
        from plugins.installed.payments.gateway import gateway_registry
        from plugins.installed.payments.models import PaymentTransaction

        order = refund.order
        slug = (getattr(order, 'payment_gateway', '') or 'stripe').strip() or 'stripe'
        tx = (
            PaymentTransaction.objects.filter(
                order=order, provider=slug, status=PaymentTransaction.Status.SUCCEEDED
            )
            .order_by('-id')
            .first()
        )
        if tx is None:
            logger.info(
                'refund: no successful %s transaction on order %s — leaving '
                'refund #%s as manual/pending.',
                slug,
                order.order_number,
                refund.id,
            )
            return

        gateway = gateway_registry.get(slug) if hasattr(gateway_registry, 'get') else None
        if gateway is None:
            # Iterate registered gateways (older registry shape).
            for g in getattr(gateway_registry, 'all', lambda: [])():
                if getattr(g, 'slug', None) == slug:
                    gateway = g
                    break
        if gateway is None:
            logger.warning('refund: gateway %r not registered.', slug)
            return
        if not getattr(gateway, 'supports_refunds', False):
            logger.info('refund: gateway %r does not support refunds — manual.', slug)
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
            'type': 'object',
            'properties': {
                'stripe_secret_key': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'Stripe Secret Key',
                },
                'stripe_public_key': {'type': 'string', 'title': 'Stripe Public Key'},
                'stripe_webhook_secret': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'Stripe Webhook Secret',
                },
                'capture_strategy': {
                    'type': 'string',
                    'enum': ['automatic', 'manual'],
                    'default': 'automatic',
                    'title': 'Capture strategy',
                },
                'paypal_enabled': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Enable PayPal',
                    'description': 'Offer PayPal at checkout (needs client ID + secret below).',
                },
                'paypal_client_id': {'type': 'string', 'title': 'PayPal Client ID'},
                'paypal_client_secret': {
                    'type': 'string',
                    'format': 'password',
                    'title': 'PayPal Client Secret',
                },
                'paypal_mode': {
                    'type': 'string',
                    'enum': ['sandbox', 'live'],
                    'default': 'sandbox',
                    'title': 'PayPal mode',
                },
                'paypal_webhook_id': {
                    'type': 'string',
                    'title': 'PayPal Webhook ID',
                    'description': 'From the PayPal developer dashboard — enables the /payments/webhooks/paypal/ backstop.',
                },
            },
        }

    def contribute_settings_panel(self):
        # Renders as a schema-driven card on the 'payments' settings category
        # page (Stripe keys + capture strategy) via admin_dashboard's generic
        # settings_category view. advanced_payments contributes its own
        # 'Advanced payments' card to the same category — two plugins, one
        # page; NOT a duplicate (ADR 0003). Disabling either removes its card.
        return SettingsPanel(
            label='Payment gateways',
            description='Stripe + PayPal credentials and capture strategy. Test + cash-on-delivery live in the Advanced payments card below.',
            schema=self.get_config_schema(),
            category='payments',
        )
