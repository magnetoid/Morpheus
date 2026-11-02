# ruff: noqa: PLC0415, I001
# Inline imports in ready()/hooks are intentional — gateway + model
# modules must not load before the app registry is ready.
import logging

from morpheus.core import events
from morpheus.app import Plugin, SettingsPanel

logger = logging.getLogger('morpheus.plugins.payments')


class PaymentsPlugin(Plugin):
    name = 'payments'
    label = 'Payments Engine'
    version = '1.0.0'
    description = (
        'Takes payment at checkout (Stripe, PayPal, bank transfer, cash on delivery and a '
        'staff-only test payment) and scores every new order for fraud risk.'
    )
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
        self.register_hook(events.HEALTH_CHECKS, self.on_health_checks, priority=20)
        # Fraud risk on every new order, and its panel on the dashboard order page.
        from plugins.installed.payments import risk

        self.register_hook(events.ORDER_PLACED, risk.on_order_placed, priority=85)
        self.register_hook(events.ORDER_DETAIL_PANELS, risk.order_panel, priority=40)

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
            from plugins.installed.payments.gateways.cod_gateway import CashOnDeliveryGateway
            from plugins.installed.payments.gateways.manual_gateway import ManualGateway
            from plugins.installed.payments.gateways.paypal_gateway import PayPalGateway
            from plugins.installed.payments.gateways.stripe_gateway import StripeGateway
            from plugins.installed.payments.gateways.test_gateway import TestPaymentGateway

            gateway_registry.register(ManualGateway())
            gateway_registry.register(StripeGateway())
            gateway_registry.register(PayPalGateway())
            gateway_registry.register(TestPaymentGateway())
            gateway_registry.register(CashOnDeliveryGateway())
        except Exception as e:  # noqa: BLE001
            logger.warning('payments: gateway registration failed: %s', e)

        # Settings → Payments saves land in PluginConfig; enabled_gateways()
        # reads PaymentGatewayConfig — project the paypal, cod and test toggles
        # across on every panel save, and seed the cod/test rows after migrate.
        try:
            from django.apps import apps
            from django.db.models.signals import post_migrate, post_save

            from plugins.installed.payments.services.offline import sync_offline_gateways
            from plugins.models import PluginConfig

            post_save.connect(
                self._on_own_config_saved,
                sender=PluginConfig,
                dispatch_uid='payments-paypal-gateway-sync',
                weak=False,
            )
            post_migrate.connect(
                sync_offline_gateways,
                sender=apps.get_app_config('payments'),
                dispatch_uid='payments-offline-gateway-sync',
            )
        except Exception as e:  # noqa: BLE001
            logger.warning('payments: gateway config-sync wiring failed: %s', e)

    @staticmethod
    def _on_own_config_saved(sender, instance, **kwargs):
        if getattr(instance, 'plugin_name', None) == 'payments':
            from plugins.installed.payments.services.offline import sync_offline_gateways
            from plugins.installed.payments.services.paypal import sync_gateway_row

            sync_gateway_row()
            sync_offline_gateways()

    def contribute_agent_tools(self) -> list:
        from plugins.installed.payments.agent_tools import order_risk_tool

        return [order_risk_tool]

    def on_health_checks(self, value, **kwargs):
        """HEALTH_CHECKS: checkout offers at least one payment method that works."""
        from plugins.installed.payments.services.routing import picker_gateways  # noqa: PLC0415

        name = 'Checkout can take payment'
        try:
            offered = [g['slug'] for g in picker_gateways()]
        except Exception as e:  # noqa: BLE001 — the failure is the finding
            value.append({'name': name, 'ok': False, 'detail': f'Could not list methods: {e}'})
            return value
        value.append(
            {
                'name': name,
                'ok': bool(offered),
                'detail': f'Offered: {", ".join(offered)}'
                if offered
                else 'No payment method is switched on and set up; every checkout fails.',
            }
        )
        return value

    def on_checkout_gateways(self, value, user=None, **kwargs):
        """CHECKOUT_GATEWAYS: enabled-gateway dicts for the checkout picker."""
        from plugins.installed.payments.services.routing import picker_gateways  # noqa: PLC0415

        return picker_gateways(user=user)

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

        # Idempotency key is bound to the REFUND, not the transaction — a second
        # partial refund on the same payment must not replay the first key.
        result = gateway.refund(
            transaction=tx, amount=refund.amount, idempotency_key=f'morph-refund-{refund.id}'
        )
        if result.get('success'):
            refund.is_processed = True
            refund.processed_at = timezone.now()
            refund.save(update_fields=['is_processed', 'processed_at'])
            order.log_event('REFUND_GATEWAY_OK', message=f'{refund.amount}')
            # Canonical post-refund event — refund email, affiliate clawback and
            # refund conversion pixel all listen here. Fired ONLY after the money
            # actually moved, so no "refunded" email is sent for a failed refund.
            from morpheus.core import MorpheusEvents, hook_registry

            hook_registry.fire(
                MorpheusEvents.PAYMENT_REFUNDED,
                refund=refund,
                order=order,
                amount=refund.amount,
            )
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
                'cod_enabled': {
                    'type': 'boolean',
                    'title': 'Enable Cash on delivery',
                    'default': True,
                },
                'cod_instructions': {
                    'type': 'string',
                    'title': 'Cash-on-delivery instructions (shown at checkout)',
                    'description': 'e.g. "Pay the courier in cash on arrival. A small COD fee may apply."',
                    'default': '',
                },
                'test_enabled': {
                    'type': 'boolean',
                    'title': 'Enable the sandbox "Test payment" method',
                    'description': 'Offered to signed-in staff only, and never charges. Leave OFF once the store is live.',
                    'default': False,
                },
                'high_value_threshold': {
                    'type': 'number',
                    'title': 'Fraud check: a first order above this amount adds risk',
                    'minimum': 0,
                    'default': 500,
                },
            },
        }

    def contribute_settings_panel(self):
        # Renders as a schema-driven card on the 'payments' settings category
        # page via admin_dashboard's generic settings_category view.
        return SettingsPanel(
            label='Payment gateways',
            description='Stripe and PayPal credentials, cash on delivery, the staff-only test payment and the fraud check.',
            schema=self.get_config_schema(),
            category='payments',
        )
