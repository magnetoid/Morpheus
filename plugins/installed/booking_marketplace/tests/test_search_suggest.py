"""Suggestions while a visitor types (GET /bookings/suggest/?q=…, read by search.js).

Every word must match: a suggestion is what was typed, never a close match. Links follow
the visitor's language, and the text is data the script sets with textContent.
"""

from __future__ import annotations

from django.test import TestCase, override_settings
from django.utils.text import slugify
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService, Place
from plugins.installed.booking_marketplace.tests._i18n import serbian_enabled
from plugins.installed.catalog.models import Category, Vendor

EMPTY = {'experiences': [], 'places': [], 'categories': []}


class SuggestFixture:
    def setUp(self):
        super().setUp()
        self.vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        categories = [
            Category.objects.create(name=f'Kotor {name}', slug=f'kotor-{name.lower()}')
            for name in ('Boats', 'Food', 'Walks', 'Wine')
        ]
        for i in range(6):
            BookableService.objects.create(
                vendor=self.vendor,
                name=f'Kotor Experience {i}',
                slug=f'kotor-experience-{i}',
                location='Kotor',
                region='kotor',
                category=categories[i % 4],
                price=Money(40 + i, 'EUR'),
            )
        for name in ('Kotor', 'Kotor Old Town', 'Kotor Fortress', 'Kotor Serpentine'):
            Place.objects.create(
                name=name,
                slug=slugify(name),
                region='kotor',
                is_active=True,
                summary='s',
                description='d',
            )

    def _json(self, q, path='/bookings/suggest/'):
        response = self.client.get(path, {'q': q})
        self.assertEqual(response.status_code, 200)
        return response.json()


@override_settings(BOOKING_LISTING_MODE=False)
class SuggestTests(SuggestFixture, TestCase):
    def test_the_shape_and_the_limits(self):
        data = self._json('kotor')
        self.assertEqual(set(data), {'experiences', 'places', 'categories'})
        self.assertEqual([len(data[k]) for k in ('experiences', 'places', 'categories')], [5, 3, 3])
        experience = data['experiences'][0]
        self.assertEqual(set(experience), {'name', 'url', 'location', 'image', 'price'})
        self.assertTrue(experience['url'].startswith('/bookings/kotor-experience-'))
        self.assertEqual(experience['location'], 'Kotor')
        self.assertIn('€', experience['price'])
        self.assertEqual(set(data['places'][0]), {'name', 'url'})
        self.assertEqual(data['places'][0], {'name': 'Kotor', 'url': '/places/kotor/'})
        self.assertEqual(set(data['categories'][0]), {'name', 'url', 'count'})
        self.assertEqual(data['categories'][0]['url'], '/bookings/?category=kotor-boats')
        self.assertEqual(data['categories'][0]['count'], 2)

    def test_too_short_or_too_long_answers_empty(self):
        self.assertEqual(self._json('k'), EMPTY)
        self.assertEqual(self._json(''), EMPTY)
        self.assertEqual(self._json('k' * 81), EMPTY)
        self.assertEqual(self._json('the'), EMPTY)  # only a stopword

    def test_it_is_never_indexed_and_briefly_cached(self):
        response = self.client.get('/bookings/suggest/', {'q': 'kotor'})
        self.assertEqual(response['X-Robots-Tag'], 'noindex')
        self.assertIn('public', response['Cache-Control'])
        self.assertIn('max-age=60', response['Cache-Control'])

    def test_only_live_experiences(self):
        hidden_host = Vendor.objects.create(name='Gone', slug='gone', is_active=False)
        BookableService.objects.create(
            vendor=hidden_host,
            name='Hidden Lagoon Tour',
            slug='hidden-lagoon',
            price=Money(1, 'EUR'),
        )
        BookableService.objects.create(
            vendor=self.vendor,
            name='Hidden Cove Map',
            slug='hidden-map',
            listing_kind='product',
            price=Money(1, 'EUR'),
        )
        BookableService.objects.create(
            vendor=self.vendor,
            name='Hidden Beach Day',
            slug='hidden-beach',
            is_active=False,
            price=Money(1, 'EUR'),
        )
        self.assertEqual(self._json('hidden')['experiences'], [])

    def test_only_what_matches_every_word(self):
        self.assertEqual(self._json('kotor zzzz'), EMPTY)

    def test_text_is_data(self):
        BookableService.objects.create(
            vendor=self.vendor,
            name='<img src=x onerror=alert(1)> Cove',
            slug='cove',
            price=Money(1, 'EUR'),
        )
        self.assertEqual(
            [e['name'] for e in self._json('cove')['experiences']],
            ['<img src=x onerror=alert(1)> Cove'],
        )

    @override_settings(BOOKING_LISTING_MODE=True)
    def test_listing_mode_shows_no_price(self):
        self.assertEqual({e['price'] for e in self._json('kotor')['experiences']}, {''})


@serbian_enabled
@override_settings(BOOKING_LISTING_MODE=False)
class SerbianSuggestTests(SuggestFixture, TestCase):
    def test_links_stay_in_serbian(self):
        data = self._json('kotor', path='/sr/bookings/suggest/')
        links = [item['url'] for group in data.values() for item in group]
        self.assertTrue(links)
        for link in links:
            with self.subTest(link=link):
                self.assertTrue(link.startswith('/sr/'), link)
