"""Permission boundary tests for the product_archive view.

`product_archive` is POST-only, `@staff_member_required`, and mutates
state (flips Product.status active↔archived). That combination — a
write endpoint behind a staff gate — is exactly where a quiet
permission leak is expensive, so we lock the triplet in:

  anon         → redirected to login, no mutation
  authed/!staff → redirected to login, no mutation
  authed/staff  → 302 back to the list, status actually flips

`@staff_member_required` redirects both anonymous and non-staff users
to the login page (302) rather than 403'ing, so the load-bearing
assertion for the first two is "the product did NOT change."
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from djmoney.money import Money

from plugins.installed.catalog.models import Product


def _make_user(email: str, *, is_staff: bool = False):
    User = get_user_model()
    return User.objects.create_user(
        username=email,
        email=email,
        password='pw',
        is_staff=is_staff,
    )


def _make_product(**kwargs):
    defaults = {
        'name': 'Archivable Book',
        'slug': 'archivable-book',
        'sku': 'ARCH-1',
        'status': 'active',
        'price': Money(Decimal('10.00'), 'USD'),
        'product_type': 'simple',
    }
    defaults.update(kwargs)
    return Product.objects.create(**defaults)


class ProductArchiveBoundaryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.product = _make_product()
        self.url = reverse('admin_dashboard:product_archive', args=[self.product.id])
        self.unscoped = _make_user('alice@example.com', is_staff=False)
        self.staff = _make_user('bob@example.com', is_staff=True)

    def test_anonymous_redirected_to_login_and_no_mutation(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.headers['Location'])
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'active')

    def test_authed_without_staff_blocked_and_no_mutation(self):
        self.client.force_login(self.unscoped)
        response = self.client.post(self.url)
        self.assertIn(response.status_code, (302, 403))
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'active')

    def test_staff_allowed_and_status_toggles(self):
        self.client.force_login(self.staff)
        # active → archived
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'archived')
        # archived → active (restore)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'active')
