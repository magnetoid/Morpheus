"""The checkout asks up front only for what a delivery needs (v0.135.0).

Under every theme, both checkout forms (the one-page form the cart links to, and the
three-step one) show email, name, street, city, region, postal code and a list of
countries. The apartment line and the phone wait behind a disclosure, which is open
when it already holds a value. The country list starts from the store's own country,
and its values are codes, because shipping zones and tax regions compare codes.
"""

from __future__ import annotations

from decimal import Decimal
from html.parser import HTMLParser

from django.apps import apps
from django.test import TestCase, override_settings
from djmoney.money import Money

from core.models import StoreSettings
from plugins.installed.catalog.models import Product
from themes.registry import theme_registry

THEMES = ['dot_books', 'supernatural_shop', 'irving_survival']
if apps.is_installed('plugins.installed.booking_marketplace'):
    THEMES.append('montenegro')

FIELDS = {
    'email',
    'first_name',
    'last_name',
    'address_line1',
    'address_line2',
    'city',
    'state',
    'postal_code',
    'country',
    'phone',
}
UP_FRONT = FIELDS - {'address_line2', 'phone'}
FORMS = {'/checkout/quick/': 'one-page', '/checkout/': 'three-step'}


class _Fields(HTMLParser):
    """Each address control by name: its tag, and whether a closed <details> hides it."""

    def __init__(self):
        super().__init__()
        self.open_details: list[bool] = []
        self.fields: dict[str, tuple[str, bool]] = {}
        self.in_select = False
        self.selected: list[str] = []
        self.options: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        name = attrs.get('name')
        if tag == 'details':
            self.open_details.append('open' in attrs)
        elif tag in ('input', 'select', 'textarea') and name in FIELDS:
            self.fields[name] = (tag, not all(self.open_details))
            self.in_select = tag == 'select'
        elif tag == 'option' and self.in_select:
            self.options.append(attrs.get('value') or '')
            if 'selected' in attrs:
                self.selected.append(attrs.get('value') or '')

    def handle_endtag(self, tag):
        if tag == 'details' and self.open_details:
            self.open_details.pop()
        elif tag == 'select':
            self.in_select = False


def _parse(response) -> _Fields:
    parser = _Fields()
    parser.feed(response.content.decode())
    return parser


class ShortCheckoutFormTests(TestCase):
    def setUp(self):
        StoreSettings.objects.create(country='GB')
        product = Product.objects.create(
            name='Short Form Book',
            slug='short-form-book',
            sku='SF-1',
            price=Money(Decimal('12.00'), 'USD'),
            status='active',
        )
        self.client.post(f'/cart/add/{product.id}/', {'quantity': 1})

    def use_theme(self, name):
        override = override_settings(MORPHEUS_ACTIVE_THEME=name)
        override.enable()
        self.addCleanup(override.disable)
        previous = theme_registry._active_name
        self.addCleanup(setattr, theme_registry, '_active_name', previous)
        theme_registry.set_active(name)

    def test_every_form_shows_eight_fields_and_tucks_away_two(self):
        for theme in THEMES:
            for url, form in FORMS.items():
                with self.subTest(theme=theme, form=form):
                    self.use_theme(theme)
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    page = _parse(response)
                    self.assertEqual(set(page.fields), FIELDS)
                    shown = {name for name, (_tag, hidden) in page.fields.items() if not hidden}
                    self.assertEqual(shown, UP_FRONT)

    def test_the_country_is_a_list_of_codes_starting_from_the_store_country(self):
        for theme in THEMES:
            for url, form in FORMS.items():
                with self.subTest(theme=theme, form=form):
                    self.use_theme(theme)
                    page = _parse(self.client.get(url))
                    self.assertEqual(page.fields['country'][0], 'select')
                    self.assertEqual(page.selected, ['GB'])
                    self.assertIn('US', page.options)
                    self.assertNotIn('EU', page.options)

    def test_a_tucked_field_that_holds_a_value_is_shown(self):
        sent = {'email': 'ada@example.com', 'phone': '+44 20 7946 0000', 'country': 'GB'}
        for theme in THEMES:
            for url, form in FORMS.items():
                with self.subTest(theme=theme, form=form):
                    self.use_theme(theme)
                    # No street: the form comes back with the error and what was typed.
                    response = self.client.post(url, sent)
                    self.assertEqual(response.status_code, 200)
                    page = _parse(response)
                    self.assertFalse(page.fields['phone'][1])
                    self.assertTrue(page.fields['address_line2'][1])
                    self.assertEqual(page.selected, ['GB'])
