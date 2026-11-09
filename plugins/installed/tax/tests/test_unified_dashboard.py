"""Unified Tax dashboard — regions + rates on one page (ADR 0003)."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class UnifiedTaxDashboardTests(TestCase):
    def setUp(self):
        u = get_user_model().objects.create_user(
            username='taxer', email='t@example.test', password='pw'
        )
        u.is_staff = True
        u.save(update_fields=['is_staff'])
        self.client.force_login(u)
        self.url = reverse('tax_dashboard:regions')

    def test_one_page_renders_regions_and_rates(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'tax/dashboard/tax.html')
        self.assertContains(r, 'Regions')
        self.assertContains(r, 'Rates')
        self.assertContains(r, 'Tax calculation')
        # Both switches are read at checkout since v0.149.0; Stripe Tax never was.
        self.assertContains(r, 'name="prices_include_tax"')
        self.assertContains(r, 'name="shipping_taxable"')
        self.assertNotContains(r, 'Stripe Tax')

    def test_config_saves_to_taxconfiguration_model(self):
        from plugins.installed.tax.models import TaxConfiguration, TaxRegion

        reg = TaxRegion.objects.create(name='EU-DE', country='DE')
        self.client.post(
            self.url,
            {
                'kind': 'config',
                'provider': 'none',
                'default_region': str(reg.id),
            },
        )
        cfg = TaxConfiguration.objects.first()
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.provider, 'none')
        self.assertEqual(cfg.default_region_id, reg.id)

    def test_create_region_then_rate_via_kind_dispatch(self):
        from plugins.installed.tax.models import TaxRate, TaxRegion

        self.client.post(
            self.url,
            {
                'kind': 'region',
                'action': 'create',
                'name': 'US-CA',
                'country': 'US',
                'region': 'CA',
            },
        )
        region = TaxRegion.objects.get(name='US-CA')
        self.client.post(
            self.url,
            {
                'kind': 'rate',
                'action': 'create',
                'name': 'CA Sales',
                'region': str(region.id),
                'rate_percent': '7.25',
                'priority': '0',
            },
        )
        self.assertTrue(TaxRate.objects.filter(name='CA Sales', region=region).exists())

    def test_delete_region_via_kind_dispatch(self):
        from plugins.installed.tax.models import TaxRegion

        reg = TaxRegion.objects.create(name='Z', country='US')
        self.client.post(self.url, {'kind': 'region', 'action': 'delete', 'region_id': str(reg.id)})
        self.assertFalse(TaxRegion.objects.filter(pk=reg.id).exists())

    def test_rates_url_redirects_to_unified_page(self):
        r = self.client.get(reverse('tax_dashboard:rates'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/dashboard/tax/regions/', r['Location'])

    def test_the_two_switches_save(self):
        from plugins.installed.tax.models import TaxConfiguration

        self.client.post(
            self.url,
            {
                'kind': 'config',
                'provider': 'local',
                'prices_include_tax': 'on',
                'shipping_taxable': 'on',
            },
        )
        cfg = TaxConfiguration.objects.get()
        self.assertTrue(cfg.prices_include_tax)
        self.assertTrue(cfg.shipping_taxable)
        self.client.post(self.url, {'kind': 'config', 'provider': 'local'})
        cfg.refresh_from_db()
        self.assertFalse(cfg.prices_include_tax)
        self.assertFalse(cfg.shipping_taxable)

    def test_a_category_is_added_and_deleted_with_its_rates(self):
        from plugins.installed.tax.models import TaxCategory, TaxRate, TaxRegion

        self.client.post(self.url, {'kind': 'category', 'action': 'create', 'name': 'Books'})
        self.assertTrue(TaxCategory.objects.filter(code='books', name='Books').exists())
        region = TaxRegion.objects.create(name='DE', country='DE')
        TaxRate.objects.create(name='VAT 7%', region=region, category_id='books', rate_percent=7)
        self.assertContains(self.client.get(self.url), 'Books')
        self.client.post(self.url, {'kind': 'category', 'action': 'delete', 'code': 'books'})
        self.assertFalse(TaxCategory.objects.exists())
        self.assertFalse(TaxRate.objects.exists())
