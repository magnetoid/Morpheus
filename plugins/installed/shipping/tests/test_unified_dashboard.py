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

    def test_one_page_renders_zones_rates_and_carriers(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'shipping/dashboard/shipping.html')
        self.assertContains(r, 'Zones')
        self.assertContains(r, 'Rates')
        self.assertContains(r, 'Carriers')

    def test_carrier_config_saves_to_plugin_config(self):
        from plugins.installed.shipping.services import _shipping_config
        from plugins.models import PluginConfig

        self.client.post(
            self.url,
            {
                'kind': 'config',
                'tax_shipping': 'on',
                'shippo_api_key': 'shippo_test_key',
                'shippo_default_address': '{"country": "US", "zip": "10001"}',
            },
        )
        cfg = PluginConfig.objects.get(plugin_name='shipping').config
        self.assertTrue(cfg['tax_shipping'])
        self.assertEqual(cfg['shippo_api_key'], 'shippo_test_key')
        self.assertEqual(cfg['shippo_default_address'], {'country': 'US', 'zip': '10001'})
        # The quote path reads via _shipping_config — it must see the same dict.
        self.assertEqual(_shipping_config()['shippo_api_key'], 'shippo_test_key')

    def test_invalid_origin_json_aborts_save(self):
        from plugins.models import PluginConfig

        self.client.post(
            self.url,
            {'kind': 'config', 'shippo_api_key': 'k', 'shippo_default_address': 'not json'},
        )
        row = PluginConfig.objects.filter(plugin_name='shipping').first()
        cfg = row.config if row else {}
        self.assertNotIn('shippo_api_key', cfg)

    def test_settings_panel_dropped(self):
        # Carrier config now lives on the unified page; the duplicate 'Shipping'
        # SettingsPanel was removed (ADR 0003), so the plugin must not override
        # the base no-op contribute_settings_panel.
        from morpheus.app import Plugin
        from plugins.installed.shipping.app import ShippingPlugin

        self.assertIs(ShippingPlugin.contribute_settings_panel, Plugin.contribute_settings_panel)

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
