"""Cash on delivery and the staff-only test payment.

Neither has a view of its own (config rides the staff-gated generic settings
flow), so the tests assert the gateway contract, the registration and the
panel → PaymentGatewayConfig bridge.
"""

from __future__ import annotations

from importlib import import_module
from types import SimpleNamespace

from django.test import TestCase

from plugins.installed.payments.gateway import PaymentGateway, gateway_registry
from plugins.installed.payments.gateways.cod_gateway import CashOnDeliveryGateway
from plugins.installed.payments.gateways.test_gateway import TestPaymentGateway
from plugins.installed.payments.models import PaymentGatewayConfig, is_enabled
from plugins.installed.payments.services.offline import sync_offline_gateways
from plugins.installed.payments.services.routing import picker_gateways
from plugins.registry import app_registry


class GatewayContractTests(TestCase):
    def setUp(self):
        # A stand-in order — the gateways only read `.id`.
        self.order = SimpleNamespace(id='00000000-0000-0000-0000-000000000001')

    def test_both_are_payment_gateways(self):
        self.assertIsInstance(TestPaymentGateway(), PaymentGateway)
        self.assertIsInstance(CashOnDeliveryGateway(), PaymentGateway)

    def test_test_gateway_succeeds_and_refunds(self):
        g = TestPaymentGateway()
        self.assertEqual(g.slug, 'test')
        intent = g.create_payment_intent(order=self.order)
        self.assertTrue(intent['success'])
        self.assertIn('test_', intent['transaction_id'])
        self.assertTrue(g.supports_refunds)
        self.assertTrue(g.refund(transaction=None, amount=None)['success'])

    def test_cod_gateway_accepts_order_without_charge(self):
        g = CashOnDeliveryGateway()
        self.assertEqual(g.slug, 'cod')
        self.assertFalse(g.supports_refunds)
        intent = g.create_payment_intent(order=self.order)
        self.assertTrue(intent['success'])
        self.assertIn('cod_', intent['transaction_id'])

    def test_registered_in_registry(self):
        # ready() runs at app load, so both gateways should be resolvable.
        self.assertIsInstance(gateway_registry.get('test'), TestPaymentGateway)
        self.assertIsInstance(gateway_registry.get('cod'), CashOnDeliveryGateway)


class PanelDrivesGatewayConfigTests(TestCase):
    """The panel (PluginConfig) must be the real control for cod/test —
    i.e. it projects onto PaymentGatewayConfig, which payments.is_enabled
    actually reads. Without this bridge the toggles are cosmetic.
    """

    def _plugin(self):
        return app_registry.get('payments')

    def test_defaults_project_cod_on_test_off(self):
        sync_offline_gateways()
        self.assertFalse(PaymentGatewayConfig.objects.get(slug='test').enabled)
        self.assertTrue(PaymentGatewayConfig.objects.get(slug='cod').enabled)
        # …and that flows through to the real enablement check + picker.
        self.assertFalse(is_enabled('test'))
        self.assertTrue(is_enabled('cod'))
        self.assertNotIn('test', {g.slug for g in gateway_registry.enabled_gateways()})

    def test_panel_save_enables_test(self):
        # Saving the panel toggle fires post_save(PluginConfig) → sync.
        self._plugin().set_config('test_enabled', True)
        self.assertTrue(is_enabled('test'))
        self._plugin().set_config('test_enabled', False)
        self.assertFalse(is_enabled('test'))

    def test_cod_instructions_reach_checkout_picker(self):
        self._plugin().set_config('cod_instructions', 'Pay the courier on arrival.')
        cod = next(p for p in picker_gateways() if p['slug'] == 'cod')
        self.assertEqual(cod['instructions'], 'Pay the courier on arrival.')


class MovedSettingsTests(TestCase):
    """advanced_payments stored the COD settings until v0.132.0. The migration that moves
    them must leave the instructions at checkout, where a sync from an empty payments
    config would have blanked them."""

    def test_moved_instructions_survive_the_next_sync(self):
        from django.apps import apps

        from plugins.models import PluginConfig

        move = import_module('plugins.migrations.0005_move_wave2_settings').Migration
        PluginConfig.objects.update_or_create(
            plugin_name='advanced_payments',
            defaults={'config': {'cod_enabled': True, 'cod_instructions': 'Cash to the courier.'}},
        )
        move.operations[0].code(apps, None)  # it moves rows; no schema editor needed
        sync_offline_gateways()
        cod = next(p for p in picker_gateways() if p['slug'] == 'cod')
        self.assertEqual(cod['instructions'], 'Cash to the courier.')
