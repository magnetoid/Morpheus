"""Permission boundary tests for the seo_inspector dashboard view.

`seo_inspector` is `@staff_member_required` and read-only, but it
resolves arbitrary catalog/CMS entities and now renders an AEO score
panel — a staff-only diagnostics surface. We lock the triplet in:

  anon          → redirected to login (302)
  authed/!staff → redirected to login (302) / forbidden (403)
  authed/staff  → 200

`@staff_member_required` redirects both anonymous and non-staff users
to the login page rather than 403'ing, so the load-bearing assertion
for the first two is "did NOT get a 200".
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from djmoney.money import Money

from plugins.installed.catalog.models import Product


def _make_user(email: str, *, is_staff: bool = False):
    user_model = get_user_model()
    return user_model.objects.create_user(
        username=email,
        email=email,
        password='pw',
        is_staff=is_staff,
    )


class SeoInspectorBoundaryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.product = Product.objects.create(
            name='Inspectable Book',
            slug='inspectable-book',
            sku='INS-1',
            status='active',
            price=Money(Decimal('12.00'), 'USD'),
        )
        # ?type=product&slug=... exercises the AEO-scoring code path.
        self.url = reverse('seo_dashboard:inspector') + '?type=product&slug=inspectable-book'
        self.unscoped = _make_user('alice@example.com', is_staff=False)
        self.staff = _make_user('bob@example.com', is_staff=True)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.headers['Location'])

    def test_authed_without_staff_blocked(self):
        self.client.force_login(self.unscoped)
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (302, 403))
        self.assertNotEqual(response.status_code, 200)

    def test_authed_with_staff_allowed_and_renders_aeo_panel(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        # The AEO panel is the new surface this view now exposes.
        self.assertContains(response, 'AEO / GEO answer-readiness')
