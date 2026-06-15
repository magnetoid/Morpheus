"""Dashboard views — permission boundaries + render without error."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()

_OVERVIEW = '/dashboard/apps/meta_commerce/overview/'
_ADS = '/dashboard/apps/meta_commerce/ads/'


class DashboardBoundaryTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='s', email='s@x.test', password='pw', is_staff=True
        )

    def _staff(self):
        c = Client()
        c.force_login(self.staff)
        return c

    def test_overview_anon_blocked(self):
        self.assertEqual(Client().get(_OVERVIEW).status_code, 302)

    def test_ads_anon_blocked(self):
        self.assertEqual(Client().get(_ADS).status_code, 302)

    def test_overview_renders_for_staff(self):
        r = self._staff().get(_OVERVIEW)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'meta-catalog.xml')

    def test_ads_renders_for_staff_when_unconnected(self):
        r = self._staff().get(_ADS)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Connect Meta Ads')

    def test_feed_url_reverses(self):
        self.assertEqual(reverse('meta_commerce:feed'), '/feeds/meta-catalog.xml')
