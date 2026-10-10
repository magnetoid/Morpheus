"""One spelling for a country: the ISO 3166-1 alpha-2 code.

Shipping zones and tax regions compare codes literally, so a shopper who typed
``UK`` (not a code — the UK is ``GB``) matched no zone and the checkout fell
back to free "Standard delivery" for any address. The store's own
``StoreSettings.country`` on Irving was ``UK`` too.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from core.utils.countries import normalise_country


class NormaliseCountryTests(SimpleTestCase):
    def test_codes_and_common_spellings(self):
        for raw, code in (
            ('gb', 'GB'),
            (' GB ', 'GB'),
            ('UK', 'GB'),
            ('United Kingdom', 'GB'),
            ('England', 'GB'),
            ('USA', 'US'),
            ('United States', 'US'),
            ('de', 'DE'),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(normalise_country(raw), code)

    def test_anything_else_is_empty(self):
        for raw in ('', None, 'Narnia', '12', 'G'):
            with self.subTest(raw=raw):
                self.assertEqual(normalise_country(raw), '')
