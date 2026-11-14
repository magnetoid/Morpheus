"""The cart's wallet buttons step aside when only the checkout form can take the order.

A wallet sheet cannot tick the terms (a required checkout field, core/checkout_fields.py)
and cannot sign anyone in, so the buttons are hidden, and the order endpoint refuses,
while the store asks for terms or takes no guest orders and the shopper is a guest.
"""

from __future__ import annotations

from plugins.installed.customers.models import Customer
from plugins.installed.payments.tests.test_express_checkout import STRIPE_READY, _Cart
from plugins.testing import set_app_settings


@STRIPE_READY
class FormOnlyTests(_Cart):
    def test_terms_to_accept_hide_the_wallets(self):
        self.assertContains(self.client.get('/cart/'), 'data-express-checkout')
        set_app_settings(self, 'orders', checkout_terms_url='/pages/terms/')
        self.assertNotContains(self.client.get('/cart/'), 'data-express-checkout')
        response = self.place(1700, str(self.standard.id))
        self.assertEqual(response.status_code, 409)

    def test_an_optional_field_keeps_them(self):
        set_app_settings(self, 'orders', checkout_order_notes=True)
        self.assertContains(self.client.get('/cart/'), 'data-express-checkout')

    def test_no_guest_orders_shows_them_to_signed_in_shoppers_only(self):
        set_app_settings(self, 'orders', allow_guest_checkout=False)
        self.assertNotContains(self.client.get('/cart/'), 'data-express-checkout')
        self.client.force_login(
            Customer.objects.create_user(email='ana@example.com', username='ana', password='x')
        )
        self.client.post(f'/cart/add/{self.product.id}/', {'quantity': 1})
        self.assertContains(self.client.get('/cart/'), 'data-express-checkout')
