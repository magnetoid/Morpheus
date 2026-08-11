"""Advanced payments — extra payment methods as modular gateways.

Stripe stays its own gateway in the ``payments`` plugin. This plugin adds
two more, registered with the same ``gateway_registry`` so they slot into
the existing payment abstraction:

* **Test payment** (slug ``test``) — a sandbox method that always
  succeeds, for trying checkout without a real processor. Off by default.
* **Cash on delivery** (slug ``cod``) — pay when the product arrives by
  mail/courier; the order is placed awaiting offline payment.

Modular: registering happens in ``ready()``, so **disabling this plugin
removes both methods from the registry** (and thus from any checkout
picker). Config lives in this plugin's PluginConfig via
``contribute_settings_panel`` (category ``payments``), not in
admin_dashboard.

Defaults: **COD on, Test off.** The settings panel is the real control —
its toggles are projected onto ``PaymentGatewayConfig`` (the table the
platform actually reads via ``payments.is_enabled``) by ``sync.py``, wired
on ``post_save`` (panel save) + ``post_migrate`` (seed) in ``ready()``.
Without that bridge the panel writes only PluginConfig, which checkout
never reads — the toggles would be cosmetic. ``cod_instructions`` rides
into the cod row's ``config['instructions']``, which the picker renders.

Checkout selection is wired (payments/services/routing.py): the storefront
picker lists ``enabled_gateways()`` and threads the chosen slug into
``create_payment_intent_for``. A disabled / unknown slug submitted at
checkout falls back to stripe server-side, so the picker can never select
a gateway that isn't enabled.
"""

# ruff: noqa: PLC0415
# Inline imports keep the manifest importable before the app registry +
# sibling payments plugin are ready (this loads at settings-import time).

from __future__ import annotations

import logging

from morpheus.app import Plugin, SettingsPanel

logger = logging.getLogger('morpheus.advanced_payments')


class AdvancedPaymentsPlugin(Plugin):
    name = 'advanced_payments'
    label = 'Advanced payments'
    version = '0.1.0'
    description = (
        'Extra payment methods as modular gateways: a sandbox "test payment" and '
        'cash on delivery (pay on arrival). Stripe stays in the payments plugin.'
    )
    has_models = False
    requires = ['payments', 'orders']

    def ready(self) -> None:
        # Register both gateways with the shared registry. Fail-soft: a
        # registration error is logged, never crashes boot (mirrors the
        # payments plugin's own ready()).
        try:
            from plugins.installed.advanced_payments.gateways.cod_gateway import (
                CashOnDeliveryGateway,
            )
            from plugins.installed.advanced_payments.gateways.test_gateway import (
                TestPaymentGateway,
            )
            from plugins.installed.payments.gateway import gateway_registry

            gateway_registry.register(TestPaymentGateway())
            gateway_registry.register(CashOnDeliveryGateway())
        except Exception as exc:  # noqa: BLE001 — never break boot over a gateway
            logger.warning('advanced_payments: gateway registration failed: %s', exc)

        # The panel toggles save to PluginConfig, but the platform reads
        # PaymentGatewayConfig (payments.is_enabled). Bridge the two so the
        # panel is the real control: resync on panel-save (post_save) and
        # seed sane defaults after migrate (post_migrate). See sync.py.
        try:
            from django.apps import apps
            from django.db.models.signals import post_migrate, post_save

            from plugins.installed.advanced_payments.sync import (
                _on_plugin_config_saved,
                sync_gateway_config,
            )
            from plugins.models import PluginConfig

            post_save.connect(
                _on_plugin_config_saved,
                sender=PluginConfig,
                dispatch_uid='advanced_payments.sync_on_config_save',
            )
            post_migrate.connect(
                sync_gateway_config,
                sender=apps.get_app_config('advanced_payments'),
                dispatch_uid='advanced_payments.sync_on_migrate',
            )
        except Exception as exc:  # noqa: BLE001 — never break boot over a signal
            logger.warning('advanced_payments: sync wiring failed: %s', exc)

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'test_enabled': {
                    'type': 'boolean',
                    'title': 'Enable the sandbox "Test payment" method',
                    'description': 'Leave OFF in production — it never charges.',
                    'default': False,
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
            },
        }

    def contribute_settings_panel(self):
        return SettingsPanel(
            label='Advanced payments',
            description='Sandbox test payments + cash on delivery. Stripe is configured separately.',
            schema=self.get_config_schema(),
            category='payments',
        )
