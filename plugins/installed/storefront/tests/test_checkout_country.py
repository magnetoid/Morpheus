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


class OnePagePrefillTests(TestCase):
    def test_a_first_visit_starts_from_the_store_country(self):
        # The one-page form threw the prefill away on a first visit until v0.135.0.
        StoreSettings.objects.create(country='UK')
        r = self.client.get('/checkout/quick/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['form'].get('country'), 'GB')

    def test_a_re_render_keeps_what_was_typed(self):
        StoreSettings.objects.create(country='UK')
        r = self.client.post('/checkout/quick/', {'email': '', 'country': 'DE'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['form'].get('country'), 'DE')


class CountryChoicesTests(SimpleTestCase):
    def test_codes_named_in_the_page_language(self):
        from core.utils.countries import country_choices

        english = dict(country_choices('en'))
        self.assertEqual(english['GB'], 'United Kingdom')
        self.assertEqual(english['ME'], 'Montenegro')
        # Serbian pages are written in Latin script, never Django's Cyrillic.
        self.assertEqual(dict(country_choices('sr'))['ME'], 'Crna Gora')

    def test_only_places_an_order_ships_to(self):
        from core.utils.countries import country_choices

        codes = [code for code, _name in country_choices('en')]
        for grouping in ('EU', 'UN', 'ZZ', 'EZ'):
            self.assertNotIn(grouping, codes)
        self.assertTrue(all(len(code) == 2 and code.isupper() for code in codes))

    def test_sorted_by_name(self):
        from core.utils.countries import country_choices

        names = [name for _code, name in country_choices('en')]
        self.assertLess(names.index('Albania'), names.index('Zimbabwe'))
        # "Åland Islands" sorts with the A's, not after Z.
        self.assertLess(names.index('Åland Islands'), names.index('Albania'))
