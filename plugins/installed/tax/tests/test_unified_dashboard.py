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
