"""Permission boundary tests for the customer-detail Affiliate toggle.

``toggle_affiliate`` is POST-only, ``@staff_member_required``, and mutates
state (creates / approves / suspends an ``affiliates.Affiliate`` for a
customer). A write endpoint behind a staff gate is exactly where a quiet
permission leak is expensive, so we lock the triplet in:

  anon          → redirected to login, no Affiliate created
  authed/!staff → blocked (302 to login), no Affiliate created
  authed/staff  → 302 back to the customer page, Affiliate toggles on/off

``@staff_member_required`` redirects both anonymous and non-staff users to
the login page (302) rather than 403'ing, so the load-bearing assertion for
the first two is "no Affiliate exists for the target customer."

`user = customers.Customer` via ``get_user_model()`` (the project's
AbstractUser subclass).
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from plugins.installed.affiliates.models import Affiliate, AffiliateProgram


def _make_user(email: str, *, is_staff: bool = False):
    User = get_user_model()
    return User.objects.create_user(
        username=email,
        email=email,
        password='pw',
        is_staff=is_staff,
    )


class CustomerAffiliateToggleBoundaryTests(TestCase):
    def setUp(self):
        self.client = Client()
        # A toggle-on needs an active program to enroll the user into.
        self.program = AffiliateProgram.objects.create(
            name='Default', slug='default', is_active=True
        )
        self.target = _make_user('target@example.com')
        self.url = reverse('affiliates_dashboard:toggle_affiliate', args=[self.target.pk])
        self.unscoped = _make_user('alice@example.com', is_staff=False)
        self.staff = _make_user('bob@example.com', is_staff=True)

    def test_anonymous_redirected_to_login_and_no_mutation(self):
        response = self.client.post(self.url, {'enable': '1'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.headers['Location'])
        self.assertFalse(Affiliate.objects.filter(user=self.target).exists())

    def test_authed_without_staff_blocked_and_no_mutation(self):
        self.client.force_login(self.unscoped)
        response = self.client.post(self.url, {'enable': '1'})
        self.assertIn(response.status_code, (302, 403))
        self.assertFalse(Affiliate.objects.filter(user=self.target).exists())

    def test_staff_allowed_and_affiliate_toggles(self):
        self.client.force_login(self.staff)
        # OFF → ON: creates an approved Affiliate for the target.
        response = self.client.post(self.url, {'enable': '1'})
        self.assertEqual(response.status_code, 302)
        affiliate = Affiliate.objects.get(user=self.target)
        self.assertEqual(affiliate.status, 'approved')
        # ON → OFF: suspends (but keeps) the Affiliate.
        response = self.client.post(self.url, {'enable': '0'})
        self.assertEqual(response.status_code, 302)
        affiliate.refresh_from_db()
        self.assertEqual(affiliate.status, 'suspended')
