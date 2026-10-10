"""Checkout stores a country code, and starts from the store's own country.

Shipping zones compare ISO codes literally, so ``UK`` (the UK is ``GB``) and
``United Kingdom`` matched no zone and the checkout fell back to free
"Standard delivery". The form also defaulted to ``US`` on a UK store.
"""

from __future__ import annotations

from django.test import SimpleTestCase, TestCase

from core.models import StoreSettings


class StepCheckoutCountryTests(TestCase):
    def test_the_posted_country_is_normalised(self):
        r = self.client.post(
            '/checkout/',
            {
                'email': 'buyer@example.com',
                'first_name': 'Ada',
                'last_name': 'Lovelace',
                'address_line1': '1 Byron Street',
                'city': 'Leeds',
                'postal_code': 'LS1 1AA',
                'country': 'United Kingdom',
            },
        )
        self.assertEqual(r.status_code, 302, r.content[:200])
        self.assertEqual(self.client.session['checkout_address']['country'], 'GB')

    def test_the_form_starts_from_the_store_country(self):
        StoreSettings.objects.create(country='UK')
        r = self.client.get('/checkout/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['form'].get('country'), 'GB')


class OnePageCheckoutCountryTests(SimpleTestCase):
    def test_shipping_input_normalises_the_country(self):
        from plugins.installed.storefront.views.checkout_one_page import _shipping_input

        self.assertEqual(_shipping_input({'country': 'uk'})['country'], 'GB')
        self.assertEqual(_shipping_input({'country': 'Narnia'})['country'], '')
