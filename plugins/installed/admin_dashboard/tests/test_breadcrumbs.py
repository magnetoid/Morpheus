"""The fallback breadcrumb follows the page's NAV location, not the URL path.

Regression for the old path-split trail that rendered
`/dashboard/apps/marketplace/vendors/` as "Dashboard › Apps › Marketplace ›
Vendors" — leaking the internal `apps` discovery-router prefix and ignoring
where the page sits in the navigation. The trail reads
"Dashboard › <Section> › [<Group>] › <Tab>" from admin_dashboard/navigation.py,
without repeating a section's own landing tab or a label equal to the one
before it.
"""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.admin_dashboard.context_processors import dashboard_breadcrumbs


class _Req:
    def __init__(self, path):
        self.path = path


def _labels(path):
    out = dashboard_breadcrumbs(_Req(path)).get('auto_breadcrumb_trail', [])
    return [c['label'] for c in out]


class NavBreadcrumbTests(TestCase):
    def test_apps_prefix_never_leaks(self):
        for path in (
            '/dashboard/apps/marketplace/vendors/',
            '/dashboard/apps/b2b/pricelists/',
            '/dashboard/apps/crm/leads/',
        ):
            self.assertNotIn('Apps', _labels(path), path)

    def test_trail_follows_nav_section(self):
        # marketplace pages are the Vendors section; its landing tab IS
        # "Vendors", so the trail does not say it twice.
        self.assertEqual(_labels('/dashboard/apps/marketplace/vendors/'), ['Dashboard', 'Vendors'])
        self.assertEqual(
            _labels('/dashboard/apps/marketplace/payouts/'), ['Dashboard', 'Vendors', 'Payouts']
        )

    def test_detail_route_resolves_to_nav_location(self):
        # A register_urls detail route (different URL tree) still resolves to
        # the owning page's place in the navigation, linking back to it.
        trail = dashboard_breadcrumbs(
            _Req('/dashboard/marketplace/vendors/3f0c9d2e-0000-4000-8000-000000000001/')
        )['auto_breadcrumb_trail']
        self.assertEqual([c['label'] for c in trail], ['Dashboard', 'Vendors'])
        # 'Vendors' is a link back to the list (it is not the leaf here).
        self.assertEqual(trail[-1]['url'], '/dashboard/apps/marketplace/vendors/')

    def test_group_label_is_not_repeated(self):
        # The affiliates list is the first page of the "Affiliates" tab group
        # in Marketing: "Marketing › Affiliates", not "… › Affiliates › Affiliates".
        self.assertEqual(
            _labels('/dashboard/apps/affiliates/list/'), ['Dashboard', 'Marketing', 'Affiliates']
        )
        self.assertEqual(
            _labels('/dashboard/apps/affiliates/programs/'),
            ['Dashboard', 'Marketing', 'Affiliates', 'Programs'],
        )

    def test_settings_tool_reads_as_settings(self):
        self.assertEqual(
            _labels('/dashboard/apps/webhooks_ui/endpoints/'),
            ['Dashboard', 'Settings', 'Developer', 'Webhooks'],
        )

    def test_core_page_uses_clean_path_fallback(self):
        # Non-registered core pages fall back to the path trail (no 'apps').
        self.assertEqual(_labels('/dashboard/products/'), ['Dashboard', 'Products'])

    def test_home_has_no_breadcrumb(self):
        self.assertEqual(_labels('/dashboard/'), [])

    def test_non_dashboard_path_ignored(self):
        self.assertEqual(dashboard_breadcrumbs(_Req('/products/')), {})
