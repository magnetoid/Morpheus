# ruff: noqa: PLC0415, I001
# Inline imports in ready()/hooks are intentional — gateway + model
# modules must not load before the app registry is ready.
import logging

from morpheus.core import events
from morpheus.app import Plugin, SettingsPanel, StorefrontBlock

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

        # Charging later (capture_mode): a parcel takes the money the card holds,
        # a cancelled order gives the hold back, and the order page shows it.
        self.register_hook(events.FULFILLMENT_CREATED, self.on_fulfillment_created, priority=20)
        self.register_hook(events.ORDER_FULFILLED, self.on_order_fulfilled, priority=20)
        self.register_hook(events.ORDER_CANCELLED, self.on_order_cancelled, priority=20)
        from plugins.installed.payments import order_panel

        self.register_hook(events.ORDER_DETAIL_PANELS, order_panel.order_panel, priority=20)
        self.register_urls(
            'plugins.installed.payments.urls_dashboard',
            prefix='dashboard/payments/',
            namespace='payments_dashboard',
        )
        # A card holds an authorization for about a week: charge or release it first.
        self.register_celery_beat(
            'payments:release_stale_authorizations',
            {'task': 'payments.release_stale_authorizations', 'schedule': 60 * 60},
        )

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

    def contribute_storefront_blocks(self) -> list:
        # Apple Pay / Google Pay / Link above the cart's checkout button, while Stripe
        # can take the payment (the tag decides; the box shows only once Stripe says
        # the browser has a wallet).
        return [
            StorefrontBlock(
                slot='cart_summary_extra',
                template='payments/blocks/express_cart.html',
                priority=10,
            ),
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.payments.agent_tools import capture_payment_tool, order_risk_tool

        return [order_risk_tool, capture_payment_tool]

    def on_fulfillment_created(self, order=None, fulfillment=None, complete=False, **kwargs):
        """FULFILLMENT_CREATED: the first parcel, or the last, takes the held money."""
        from plugins.installed.payments.services.capture import schedule_capture, stored_mode

        if order is None:
            return
        mode = stored_mode(order)
        if mode == 'first_parcel' or (mode == 'all_shipped' and complete):
            schedule_capture(order)

    def on_order_fulfilled(self, order=None, **kwargs):
        """ORDER_FULFILLED: an order fulfilled without a parcel (GraphQL, an
        agent) is charged too, in either parcel mode. A parcel's own
        FULFILLMENT_CREATED charges an order that has one."""
        from plugins.installed.payments.services.capture import (
            PARCEL_MODES,
            schedule_capture,
            stored_mode,
        )

        if order is None or stored_mode(order) not in PARCEL_MODES:
            return
        if order.fulfillments.exists():
            return
        schedule_capture(order)

    def on_order_cancelled(self, order=None, **kwargs):
        """ORDER_CANCELLED: a cancelled order's hold is always given back."""
        from plugins.installed.payments.services.capture import schedule_release

        if order is not None:
            schedule_release(order, 'The order was cancelled, so the held payment was released')

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
        self._capture_health(value, offered)
        return value

    @staticmethod
    def _capture_health(value, offered) -> None:
        """While cards are charged later, Stripe must tell the store about a
        held payment, or the order looks unpaid and expires."""
        from plugins.installed.payments.services.capture import setting_mode  # noqa: PLC0415
        from plugins.installed.payments.services.stripe import PaymentService  # noqa: PLC0415

        if 'stripe' not in offered or setting_mode() == 'immediate':
            return
        needed = ('payment_intent.amount_capturable_updated', 'payment_intent.canceled')
        sends = PaymentService.webhook_sends(needed)
        if sends is None:
            return
        value.append(
            {
                'name': 'Stripe tells the store about held card payments',
                'ok': sends,
                'detail': 'The Stripe webhook sends the held-payment events.'
                if sends
                else 'Cards are charged later, but no Stripe webhook to this store sends '
                + ' and '.join(needed)
                + '. Add them to the webhook in your Stripe dashboard, or held orders '
                'look unpaid and are cancelled after the pending-order window.',
            }
        )

    def on_checkout_gateways(self, value, user=None, ships=True, **kwargs):
        """CHECKOUT_GATEWAYS: enabled-gateway dicts for the checkout picker
        (no cash on delivery when ``ships`` is False)."""
        from plugins.installed.payments.services.routing import picker_gateways  # noqa: PLC0415

        return picker_gateways(user=user, ships=ships)

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
                'express_on_cart': {
                    'type': 'boolean',
                    'default': True,
                    'title': 'Show express checkout on the cart page',
                    'description': "Apple Pay, Google Pay and Link buttons above the cart's checkout button, while Stripe is set up. The shopper pays from their wallet without filling in the checkout form.",
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
                'capture_mode': {
                    'type': 'string',
                    'enum': ['immediate', 'first_parcel', 'all_shipped', 'manual'],
                    'default': 'immediate',
                    'title': 'When card payments are charged',
                    'description': 'immediate: at checkout. first_parcel: the card is held at checkout and charged when the first parcel is recorded. all_shipped: charged when the last parcel is recorded. manual: charged when you press Charge on the order (or ask Linda). An order with a download is charged at checkout in both parcel modes, and in manual mode its download waits until you charge it. Cancelling an order gives its hold back. Stripe must send payment_intent.amount_capturable_updated and payment_intent.canceled to the store.',
                },
                'authorization_days': {
                    'type': 'integer',
                    'minimum': 1,
                    'maximum': 6,
                    'default': 6,
                    'title': 'Days a held card payment waits',
                    'description': 'A card holds the money for about seven days. After this many days the hold is settled as below.',
                },
                'authorization_expiry': {
                    'type': 'string',
                    'enum': ['capture', 'release'],
                    'default': 'capture',
                    'title': 'When a hold reaches its time limit',
                    'description': 'capture: charge it, so the sale is not lost. release: give it back without charging; the order stays open and unpaid until you cancel it.',
                },
                'checkout_show_saved_cards': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Show saved cards at checkout',
                    'description': 'Signed-in shoppers see the cards they saved before (Stripe).',
                },
                'checkout_offer_save_card': {
                    'type': 'boolean',
                    'default': False,
                    'title': 'Offer to save the card at checkout',
                    'description': 'Signed-in shoppers can tick "save this card" for their next order (Stripe).',
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
            description='Stripe and PayPal credentials, when cards are charged, saved cards, express checkout on the cart page, cash on delivery, the staff-only test payment and the fraud check.',
            schema=self.get_config_schema(),
            category='payments',
        )
