"""The fallback breadcrumb follows the page's NAV location, not the URL path.

Regression for the old path-split trail that rendered
`/dashboard/apps/marketplace/vendors/` as "Dashboard › Apps › Marketplace ›
Vendors" — leaking the internal `apps` discovery-router prefix and ignoring
where the page sits in the sidebar. The trail now reads
"Dashboard › <Section> › <Page>" from the DashboardPage registry.
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
        # marketplace pages live in the 'marketplace' section → "Multivendor".
        self.assertEqual(
            _labels('/dashboard/apps/marketplace/vendors/'),
            ['Dashboard', 'Multivendor', 'Vendors'],
        )

    def test_detail_route_resolves_to_nav_location(self):
        # A register_urls detail route (different URL tree) still resolves to
        # the owning page's nav location, with the page linking back.
        trail = dashboard_breadcrumbs(
            _Req('/dashboard/marketplace/vendors/3f0c9d2e-0000-4000-8000-000000000001/')
        )['auto_breadcrumb_trail']
        self.assertEqual([c['label'] for c in trail], ['Dashboard', 'Multivendor', 'Vendors'])
        # 'Vendors' is a link back to the list (it is not the leaf here).
        self.assertEqual(trail[-1]['url'], '/dashboard/apps/marketplace/vendors/')

    def test_section_dedup_when_it_equals_page_label(self):
        # growth section is labelled "Affiliates"; don't render "Affiliates ›
        # Affiliates" for the affiliates landing page.
        self.assertEqual(_labels('/dashboard/apps/affiliates/list/'), ['Dashboard', 'Affiliates'])

    def test_core_page_uses_clean_path_fallback(self):
        # Non-registered core pages fall back to the path trail (no 'apps').
        self.assertEqual(_labels('/dashboard/products/'), ['Dashboard', 'Products'])

    def test_home_has_no_breadcrumb(self):
        self.assertEqual(_labels('/dashboard/'), [])

    def test_non_dashboard_path_ignored(self):
        self.assertEqual(dashboard_breadcrumbs(_Req('/products/')), {})
