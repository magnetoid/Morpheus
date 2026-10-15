"""The home page has one search bar and links categories by slug.

The hero carried its own copy of the search form and four category pills, so the page
showed the categories three times; and every category link used the name, which the
filter matched loosely while the menu's slug links found nothing.
"""

from __future__ import annotations

from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.booking_marketplace.context_processors import _nav_categories
from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Category, Vendor


@override_settings(BOOKING_LISTING_MODE=False)
class HomeSearchTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        super().setUp()
        vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        water = Category.objects.create(name='Water Sports', slug='water-sports')
        BookableService.objects.create(
            vendor=vendor,
            name='Sunset Kayak Tour',
            slug='kotor-kayak',
            region='kotor',
            category=water,
            price=Money(50, 'EUR'),
        )

    def _home(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _hero(self, body):
        start = body.rfind('<section', 0, body.index('data-mx-search="hero"'))
        return body[start : body.index('</section>', start)]

    def test_one_search_bar(self):
        body = self._home()
        self.assertEqual(body.count('data-mx-search='), 1)
        self.assertIn('data-mx-search="hero"', body)
        self.assertEqual(body.count('name="q"'), 1)

    def test_the_hero_has_no_category_pills(self):
        self.assertNotIn('/bookings/?category=', self._hero(self._home()))

    def test_the_hero_lets_the_suggestions_open_below_it(self):
        hero = self._hero(self._home())
        self.assertNotIn('overflow-hidden', hero[: hero.index('>')])

    def test_category_links_use_the_slug(self):
        body = self._home()
        self.assertIn('href="/bookings/?category=water-sports"', body)
        self.assertNotIn('category=Water', body)

    def test_the_menu_links_categories_by_slug(self):
        self.assertEqual(
            [tile['href'] for tile in _nav_categories()], ['/bookings/?category=water-sports']
        )
