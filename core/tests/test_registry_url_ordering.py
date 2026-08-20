"""Plugin URL mounts resolve most-specific-prefix first.

admin_dashboard's `dashboard/` urlconf carries the app-discovery router
(`apps/<str:plugin>/<slug:slug>/`) and used to mount before the plugins it
routes for, so a plugin's own `dashboard/apps/<name>/<route>/` was unreachable
whenever <route> wasn't a DashboardPage slug — bookvault's connect/disconnect
shipped dead this way with every test green. `get_urlpatterns` now mounts
deeper prefixes first; these tests pin the mechanism through the LIVE resolver
(resolving against the real root urlconf, not a rebuilt pattern list — the
lesson of test_registry_url_disable).
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import resolve


class UrlMountOrderingTests(TestCase):
    def test_plugin_route_beats_the_discovery_router(self):
        """bookvault's connect/ is its own view again, not a discovery 404."""
        match = resolve('/dashboard/apps/bookvault/connect/')
        self.assertEqual(match.func.__module__, 'plugins.installed.bookvault.views')
        self.assertEqual(match.func.__name__, 'connect')

    def test_discovery_still_routes_dashboard_page_slugs(self):
        """A slug a plugin did NOT mount itself still falls through to the
        discovery router — feedback's list page is a DashboardPage only."""
        match = resolve('/dashboard/apps/feedback/tickets/')
        self.assertEqual(match.func.__name__, 'plugin_page_router')

    def test_shell_pages_unaffected(self):
        match = resolve('/dashboard/products/')
        self.assertEqual(
            match.func.__module__.rsplit('.', 2)[0],
            'plugins.installed.admin_dashboard',
        )

    def test_equal_prefixes_keep_registration_order(self):
        """The sort is stable: same-depth prefixes keep first-registrant-wins
        (the newsletter-vs-storefront rule CLAUDE.md documents). Guarded by
        construction — a tie must not reorder, so the storefront root keeps
        resolving exactly as registered."""
        match = resolve('/newsletter/subscribe/')
        self.assertEqual(match.func.__module__, 'plugins.installed.newsletter.views')
