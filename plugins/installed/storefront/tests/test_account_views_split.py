"""Smoke test the account views after the split — auth gates still
enforce, view functions are still importable as views.account_home etc.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class AccountViewsSplitTests(TestCase):
    """Make sure the views/ package split didn't break the auth gates
    on the account-area views (account_home / account_orders /
    account_addresses / account_credits / account_downloads).
    """

    def setUp(self):
        self.client = Client()

    def test_views_module_still_imports(self):
        """URL conf imports `from . import views`; that has to work."""
        from plugins.installed.storefront import views

        # Sample re-exports — if these break, urls.py breaks.
        for name in (
            'home',
            'product_list',
            'product_detail',
            'cart',
            'cart_add',
            'checkout',
            'account_home',
            'account_orders',
            'vendors_directory',
            'quick_search',
            'newsletter_subscribe',
        ):
            self.assertTrue(
                hasattr(views, name),
                f'views.{name} no longer re-exported from the views/ package',
            )

    def test_account_home_anon_redirects(self):
        resp = self.client.get('/account/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp['Location'])

    def test_account_orders_anon_redirects(self):
        resp = self.client.get('/account/orders/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp['Location'])

    def test_account_credits_anon_redirects(self):
        resp = self.client.get('/account/credits/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp['Location'])

    def test_account_downloads_anon_redirects(self):
        resp = self.client.get('/account/downloads/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp['Location'])

    def test_account_home_authed_200(self):
        user = get_user_model().objects.create_user(
            username='acc@example.com',
            email='acc@example.com',
            password='pw',
        )
        self.client.force_login(user)
        resp = self.client.get('/account/')
        # Smoke: the page renders without exploding on a fresh user with
        # zero orders / zero returns / zero credit / zero downloads.
        self.assertEqual(resp.status_code, 200)
