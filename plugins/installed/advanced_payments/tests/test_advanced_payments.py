"""Unit tests for the advanced_payments gateways.

No HTTP views ship in this plugin (config rides the staff-gated generic
settings flow), so the permission-boundary triplet doesn't apply here —
the tests assert the gateway contract + the modular registration instead.
"""

from __future__ import annotations

from types import SimpleNamespace

from django.test import TestCase

from plugins.installed.advanced_payments.gateways.cod_gateway import CashOnDeliveryGateway
from plugins.installed.advanced_payments.gateways.test_gateway import TestPaymentGateway
from plugins.installed.advanced_payments.sync import sync_gateway_config
from plugins.installed.payments.gateway import PaymentGateway, gateway_registry
from plugins.installed.payments.models import PaymentGatewayConfig, is_enabled
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
        return app_registry.get('advanced_payments')

    def test_defaults_project_cod_on_test_off(self):
        sync_gateway_config()
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
