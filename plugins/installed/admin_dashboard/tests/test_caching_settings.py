"""Caching settings page — image-optimization trigger (ADR 0005) + the
HttpResponseRedirect save-path regression (commit 386d3e9).

The page is `@staff_member_required` and every POST ends in a redirect;
before the fix, that redirect raised NameError -> 500 on every save.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class CachingSettingsTests(TestCase):
    def setUp(self):
        u = get_user_model().objects.create_user(
            username='cache-admin', email='c@example.test', password='pw', is_staff=True
        )
        self.client.force_login(u)
        self.url = reverse('admin_dashboard:settings_category', args=['caching'])

    def test_page_renders_optimize_button(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Optimize existing images')

    def test_optimize_images_enqueues_task(self):
        with patch('plugins.installed.seo.tasks.optimize_images_task.delay') as delay:
            r = self.client.post(self.url, {'action': 'optimize_images', 'avif': 'on'})
        self.assertEqual(r.status_code, 302)
        delay.assert_called_once_with(avif=True)

    def test_optimize_images_failsoft_when_broker_down(self):
        with patch(
            'plugins.installed.seo.tasks.optimize_images_task.delay',
            side_effect=RuntimeError('broker down'),
        ):
            r = self.client.post(self.url, {'action': 'optimize_images'})
        # Broker failure is reported, not a 500.
        self.assertEqual(r.status_code, 302)

    def test_save_storefront_does_not_500(self):
        # Regression: settings_caching used HttpResponseRedirect out of scope.
        r = self.client.post(
            self.url,
            {
                'action': 'save_storefront',
                'html_cache_control': 'public, max-age=0',
                'asset_max_age_seconds': '60',
                'graphql_edge_cache_ttl': '0',
            },
        )
        self.assertEqual(r.status_code, 302)


class CachingCloudflareControlsTests(TestCase):
    def setUp(self):
        from plugins.installed.cloudflare.models import CloudflareAccount, CloudflareZone

        u = get_user_model().objects.create_user(
            username='cf-admin', email='cf@example.test', password='pw', is_staff=True
        )
        self.client.force_login(u)
        self.url = reverse('admin_dashboard:settings_category', args=['caching'])
        acct = CloudflareAccount.objects.create(label='acme', api_token='tok')
        self.zone = CloudflareZone.objects.create(
            account=acct, zone_id='zone123', domain='shop.example'
        )

    def test_cf_patch_setting_dispatches(self):
        with patch('plugins.installed.cloudflare.services.patch_zone_setting') as patch_fn:
            r = self.client.post(
                self.url,
                {
                    'action': 'cf_patch_setting',
                    'zone_id': str(self.zone.id),
                    'setting_id': 'cache_level',
                    'value': 'aggressive',
                },
            )
        self.assertEqual(r.status_code, 302)
        patch_fn.assert_called_once_with(self.zone, 'cache_level', 'aggressive')

    def test_cf_browser_ttl_coerced_to_int(self):
        with patch('plugins.installed.cloudflare.services.patch_zone_setting') as patch_fn:
            self.client.post(
                self.url,
                {
                    'action': 'cf_patch_setting',
                    'zone_id': str(self.zone.id),
                    'setting_id': 'browser_cache_ttl',
                    'value': '7200',
                },
            )
        patch_fn.assert_called_once_with(self.zone, 'browser_cache_ttl', 7200)

    def test_cf_patch_rejects_non_cache_setting(self):
        with patch('plugins.installed.cloudflare.services.patch_zone_setting') as patch_fn:
            r = self.client.post(
                self.url,
                {
                    'action': 'cf_patch_setting',
                    'zone_id': str(self.zone.id),
                    'setting_id': 'security_level',
                    'value': 'high',
                },
            )
        self.assertEqual(r.status_code, 302)
        patch_fn.assert_not_called()

    def test_cf_purge_all_dispatches(self):
        with patch('plugins.installed.cloudflare.services.purge_everything') as purge_fn:
            r = self.client.post(self.url, {'action': 'cf_purge_all', 'zone_id': str(self.zone.id)})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(purge_fn.call_count, 1)
        self.assertEqual(purge_fn.call_args.kwargs['zone'], self.zone)
