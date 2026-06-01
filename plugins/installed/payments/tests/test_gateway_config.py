"""Unit tests for the gateway enable-state helpers.

``is_enabled`` is the single source of truth for whether a gateway is
on, and the registry's ``enabled_gateways()`` filters by it. Defaults
matter: a fresh install (no ``PaymentGatewayConfig`` rows) must report
stripe + manual as enabled so checkout never has zero methods.
"""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.payments.gateway import gateway_registry
from plugins.installed.payments.models import (
    DEFAULT_ENABLED,
    PaymentGatewayConfig,
    is_enabled,
)


class IsEnabledDefaultsTests(TestCase):
    def test_default_enabled_set(self):
        self.assertEqual(DEFAULT_ENABLED, {'stripe', 'manual'})

    def test_unconfigured_falls_back_to_defaults(self):
        # No rows → defaults apply.
        self.assertTrue(is_enabled('stripe'))
        self.assertTrue(is_enabled('manual'))
        self.assertFalse(is_enabled('paypal'))

    def test_explicit_row_overrides_default(self):
        PaymentGatewayConfig.objects.create(slug='stripe', enabled=False)
        self.assertFalse(is_enabled('stripe'))
        PaymentGatewayConfig.objects.create(slug='paypal', enabled=True)
        self.assertTrue(is_enabled('paypal'))


class EnabledGatewaysTests(TestCase):
    def test_registry_filters_by_enabled(self):
        # Both ship enabled by default → both appear.
        slugs = {g.slug for g in gateway_registry.enabled_gateways()}
        self.assertIn('stripe', slugs)
        self.assertIn('manual', slugs)

        # Disable manual → drops out; default() (checkout) unaffected.
        PaymentGatewayConfig.objects.create(slug='manual', enabled=False)
        slugs = {g.slug for g in gateway_registry.enabled_gateways()}
        self.assertNotIn('manual', slugs)
        self.assertIn('stripe', slugs)
        self.assertIsNotNone(gateway_registry.default())
