"""Channels overview — filter aggregation + dashboard boundary."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase

User = get_user_model()


class OverviewTests(TestCase):
    def setUp(self):
        cache.delete('channels:overview:v1')
        self.staff = User.objects.create_user(
            username='s', email='s@x.test', password='pw', is_staff=True
        )

    def _staff(self):
        c = Client()
        c.force_login(self.staff)
        return c

    def test_filter_aggregates_every_channel(self):
        from plugins.installed.channels.views import _rows

        rows = _rows(refresh=True)
        names = {r['name'] for r in rows}
        # All eight commerce channels contribute a row.
        self.assertEqual(
            names,
            {
                'google_shopping',
                'meta_commerce',
                'tiktok_commerce',
                'pinterest_commerce',
                'microsoft_commerce',
                'amazon_ads',
                'reddit_ads',
                'snapchat_commerce',
            },
        )
        # Every row carries the contract keys.
        for r in rows:
            for key in ('label', 'connected', 'has_feed', 'dashboard_url'):
                self.assertIn(key, r)

    def test_boundary_and_render(self):
        self.assertEqual(Client().get('/dashboard/apps/channels/overview/').status_code, 302)
        r = self._staff().get('/dashboard/apps/channels/overview/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Sales Channels')
        self.assertContains(r, 'Snapchat')
        self.assertContains(r, 'Google')
