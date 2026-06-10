"""grant_demo_access — affiliate + vendor + gateway enablement, idempotent."""

# ruff: noqa: PLC0415
from __future__ import annotations

from unittest import skipUnless

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

_DEMO_INSTALLED = apps.is_installed('plugins.installed.demo_data')


@skipUnless(_DEMO_INSTALLED, 'demo_data is opt-in (not in MORPHEUS_DEFAULT_PLUGINS)')
class GrantDemoAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='marko',
            email='marko@example.test',
            password='pw',
        )

    def test_grants_affiliate_vendor_and_gateways(self):
        call_command('grant_demo_access', '--email', 'marko@example.test')

        from plugins.installed.affiliates.models import Affiliate
        from plugins.installed.catalog.models import Vendor
        from plugins.installed.payments.models import PaymentGatewayConfig

        aff = Affiliate.objects.filter(user=self.user).first()
        self.assertIsNotNone(aff)
        self.assertEqual(aff.status, 'approved')

        vendor = Vendor.objects.filter(owner=self.user).first()
        self.assertIsNotNone(vendor)
        self.assertTrue(vendor.is_active)

        self.assertTrue(PaymentGatewayConfig.objects.get(slug='cod').enabled)
        self.assertTrue(PaymentGatewayConfig.objects.get(slug='test').enabled)

    def test_idempotent(self):
        call_command('grant_demo_access', '--email', 'marko@example.test')
        call_command('grant_demo_access', '--email', 'marko@example.test')
        from plugins.installed.affiliates.models import Affiliate
        from plugins.installed.catalog.models import Vendor

        self.assertEqual(Affiliate.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Vendor.objects.filter(owner=self.user).count(), 1)

    def test_cod_only_skips_test_gateway(self):
        call_command('grant_demo_access', '--email', 'marko@example.test', '--cod-only')
        from plugins.installed.payments.models import PaymentGatewayConfig

        self.assertTrue(PaymentGatewayConfig.objects.get(slug='cod').enabled)
        self.assertFalse(PaymentGatewayConfig.objects.filter(slug='test').exists())
