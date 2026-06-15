"""Dashboard views — permission boundaries + they render without error.

Mandatory boundary tests for new staff-facing views (CLAUDE.md): anonymous is
blocked, staff gets a 200. Rendering staff-side also proves the templates load
and the coverage/ads code paths don't raise when unconfigured.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()

_OVERVIEW = '/dashboard/apps/google_shopping/overview/'
_ADS = '/dashboard/apps/google_shopping/ads/'


class DashboardBoundaryTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='s', email='s@x.test', password='pw', is_staff=True
        )

    def _staff(self):
        c = Client()
        c.force_login(self.staff)
        return c

    def test_overview_anonymous_blocked(self):
        self.assertEqual(Client().get(_OVERVIEW).status_code, 302)

    def test_ads_anonymous_blocked(self):
        self.assertEqual(Client().get(_ADS).status_code, 302)

    def test_overview_renders_for_staff(self):
        r = self._staff().get(_OVERVIEW)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'google-merchant.xml')

    def test_ads_renders_for_staff_when_unconnected(self):
        r = self._staff().get(_ADS)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Connect Google Ads')

    def test_feed_url_reverses(self):
        # The public feed endpoint is named and mounted at site root.
        self.assertEqual(reverse('google_shopping:feed'), '/feeds/google-merchant.xml')
