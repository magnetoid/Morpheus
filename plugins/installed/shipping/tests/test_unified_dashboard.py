"""Unified Shipping dashboard — zones + rates CRUD on one page (ADR 0003)."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class UnifiedShippingDashboardTests(TestCase):
    def setUp(self):
        u = get_user_model().objects.create_user(
            username='ship', email='s@example.test', password='pw'
        )
        u.is_staff = True
        u.save(update_fields=['is_staff'])
        self.client.force_login(u)
        self.url = reverse('shipping_dashboard:zones')

    def test_one_page_renders_zones_and_rates(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'shipping/dashboard/shipping.html')
        self.assertContains(r, 'Zones')
        self.assertContains(r, 'Rates')

    def test_create_zone_then_rate_via_kind_dispatch(self):
        from plugins.installed.shipping.models import ShippingRate, ShippingZone

        self.client.post(
            self.url, {'kind': 'zone', 'action': 'create', 'name': 'US', 'countries': 'US'}
        )
        zone = ShippingZone.objects.get(name='US')
        self.client.post(
            self.url,
            {
                'kind': 'rate',
                'action': 'create',
                'name': 'Ground',
                'zone': str(zone.id),
                'computation': 'flat',
                'flat_amount': '5.00',
                'priority': '50',
                'is_active': 'on',
            },
        )
        self.assertTrue(ShippingRate.objects.filter(name='Ground', zone=zone).exists())

    def test_delete_zone_via_kind_dispatch(self):
        from plugins.installed.shipping.models import ShippingZone

        z = ShippingZone.objects.create(name='Z', countries=['US'])
        self.client.post(self.url, {'kind': 'zone', 'action': 'delete', 'zone_id': str(z.id)})
        self.assertFalse(ShippingZone.objects.filter(pk=z.id).exists())

    def test_rates_url_redirects_to_unified_page(self):
        r = self.client.get(reverse('shipping_dashboard:rates'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/dashboard/shipping/zones/', r['Location'])
