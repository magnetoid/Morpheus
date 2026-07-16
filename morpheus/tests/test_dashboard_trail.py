"""dashboard_trail — the SDK's shared breadcrumb builder for plugin dashboard
pages (replaces the per-plugin ``_trail`` copies and the admin_dashboard-owned
``build_trail``, which had eight plugins importing a sibling plugin)."""

from __future__ import annotations

from django.test import SimpleTestCase

from morpheus import dashboard_trail


class DashboardTrailTests(SimpleTestCase):
    def test_builds_dashboard_rooted_trail(self):
        self.assertEqual(
            dashboard_trail('Tax', '/dashboard/tax/regions/'),
            [
                {'label': 'Dashboard', 'url': '/dashboard/'},
                {'label': 'Tax', 'url': '/dashboard/tax/regions/'},
            ],
        )

    def test_items_accept_dicts_and_strings(self):
        trail = dashboard_trail(
            'Shipping',
            '/dashboard/shipping/zones/',
            {'label': 'Zones', 'url': '/dashboard/shipping/zones/'},
            'Edit',
        )
        self.assertEqual(trail[2], {'label': 'Zones', 'url': '/dashboard/shipping/zones/'})
        self.assertEqual(trail[3], {'label': 'Edit'})  # string → unlinked leaf crumb
