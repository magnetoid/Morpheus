"""The experiences and shop lists answer what the search bar asked (views + search_page).

Live on 2026-10-14 a multi-word search found nothing, the date was never read, the menu's
category links (`?category=water-sports`) showed 0 results, and results came in the
recommended order whatever was typed.
"""

from __future__ import annotations

import datetime
import types
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone, translation
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.booking_marketplace import search_page
from plugins.installed.booking_marketplace.models import BookableService, Booking
from plugins.installed.catalog.models import Category, Vendor

P = search_page.SearchParams
WATER = types.SimpleNamespace(name='Water Sports', slug='water-sports')
SUNDAY = datetime.date(2026, 10, 18)


class SearchFixture:
    def setUp(self):
        super().setUp()
        vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        self.water = Category.objects.create(name='Water Sports', slug='water-sports')
        culture = Category.objects.create(name='Culture', slug='culture')

        def listing(
            slug,
            name,
            *,
            location='',
            region='',
            category=culture,
            description='',
            kind='experience',
        ):
            return BookableService.objects.create(
                vendor=vendor,
                slug=slug,
                name=name,
                location=location,
                region=region,
                category=category,
                description=description,
                listing_kind=kind,
                price=Money(50, 'EUR'),
                daily_capacity=4,
            )

        self.kotor_kayak = listing(
            'kotor-kayak',
            'Sunset Kayak Tour on the Bay of Kotor',
            location='Kotor',
            region='kotor',
            category=self.water,
        )
        listing(
            'budva-kayak',
            'Kayak and Snorkel Tour to Sveti Nikola Island',
            location='Budva',
            region='budva',
            category=self.water,
        )
        listing(
            'kotor-walk',
            'Kotor Old Town Walk',
            location='Kotor',
            region='kotor',
            description='Ends at the kayak harbour.',
        )
        listing('zabljak-hike', 'Durmitor Day Hike', location='Žabljak', region='durmitor')
        listing('wild-honey', 'Wild Mountain Honey', kind='product')
        self.day = timezone.localdate() + datetime.timedelta(days=5)

    def _get(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response

    def _slugs(self, path):
        return [s.slug for s in self._get(path).context['services']]

    def _search(self, path):
        return self._get(path).context['search']


@override_settings(BOOKING_LISTING_MODE=False)
class ExperienceResultsTests(SearchFixture, TestCase):
    def test_every_word_in_any_order_best_match_first(self):
        self.assertEqual(self._slugs('/bookings/?q=kayak+kotor'), ['kotor-kayak', 'kotor-walk'])
        self.assertEqual(self._slugs('/bookings/?q=kotor+kayak'), ['kotor-kayak', 'kotor-walk'])

    def test_accents_serbian_and_typos(self):
        self.assertEqual(self._slugs('/bookings/?q=zabljak'), ['zabljak-hike'])
        kayaks = {'kotor-kayak', 'budva-kayak', 'kotor-walk'}
        self.assertEqual(set(self._slugs('/bookings/?q=kajak')), kayaks)
        self.assertEqual(set(self._slugs('/bookings/?q=kayac')), kayaks)

    def test_close_matches_when_no_listing_has_every_word(self):
        response = self._get('/bookings/?q=kayak+ulcinj')
        self.assertTrue(response.context['search']['close'])
        self.assertEqual(
            {s.slug for s in response.context['services']},
            {'kotor-kayak', 'budva-kayak', 'kotor-walk'},
        )

    def test_close_matches_stay_inside_the_filters(self):
        self.assertEqual(self._slugs('/bookings/?q=kayak+ulcinj&region=budva'), ['budva-kayak'])

    def test_category_by_slug_or_name_in_any_case(self):
        for value in ('water-sports', 'Water+Sports', 'WATER-SPORTS', 'water+sports'):
            with self.subTest(value=value):
                self.assertEqual(
                    set(self._slugs(f'/bookings/?category={value}')), {'kotor-kayak', 'budva-kayak'}
                )
        self.assertEqual(
            self._get('/bookings/?category=Water+Sports').context['category'], 'water-sports'
        )

    def test_an_unknown_category_or_region_is_ignored(self):
        self.assertEqual(len(self._slugs('/bookings/?category=nope')), 4)
        self.assertEqual(self._search('/bookings/?category=nope')['category'], '')
        self.assertEqual(len(self._slugs('/bookings/?region=narnia')), 4)
        self.assertEqual(self._search('/bookings/?region=narnia')['region'], '')

    def test_a_date_drops_what_is_full_that_day(self):
        Booking.objects.create(
            service=self.kotor_kayak,
            customer_name='A',
            customer_email='a@example.com',
            booking_date=self.day,
            guests=4,
            status='confirmed',
        )
        path = f'/bookings/?date={self.day.isoformat()}'
        self.assertEqual(set(self._slugs(path)), {'budva-kayak', 'kotor-walk', 'zabljak-hike'})
        self.assertEqual(self._search(path)['date_iso'], self.day.isoformat())

    def test_a_past_date_is_ignored_with_a_note(self):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        response = self._get(f'/bookings/?date={yesterday.isoformat()}')
        self.assertEqual(len(response.context['services']), 4)
        self.assertEqual(response.context['search']['date_note'], 'Choose a date from today on')
        self.assertEqual(response.context['search']['date_iso'], '')

    def test_today_counts_and_nonsense_is_ignored(self):
        today = timezone.localdate().isoformat()
        self.assertEqual(self._search(f'/bookings/?date={today}')['date_iso'], today)
        nonsense = self._search('/bookings/?date=2026-13-45')
        self.assertEqual((nonsense['date_iso'], nonsense['date_note']), ('', ''))

    def test_everything_together(self):
        path = f'/bookings/?q=kayak&region=kotor&category=water-sports&date={self.day.isoformat()}'
        self.assertEqual(self._slugs(path), ['kotor-kayak'])

    def test_the_order(self):
        self.assertEqual(self._get('/bookings/?q=kayak').context['sort'], 'best')
        self.assertEqual(self._get('/bookings/').context['sort'], 'recommended')
        self.assertEqual(self._get('/bookings/?sort=best').context['sort'], 'recommended')
        self.assertEqual(self._get('/bookings/?q=kayak&sort=rating').context['sort'], 'rating')
        self.assertEqual(self._get('/bookings/?sort=nonsense').context['sort'], 'recommended')

    def test_a_huge_query_still_answers(self):
        response = self._get('/bookings/?q=' + 'kayak+' * 2000)
        self.assertLessEqual(len(response.context['q']), 200)

    def test_a_search_is_reported(self):
        with mock.patch.object(hook_registry, 'fire', wraps=hook_registry.fire) as fire:
            self._get('/bookings/?q=kayak+kotor')
            self._get('/bookings/?q=kayak+ulcinj')
            self._get('/bookings/?region=kotor')
        searches = [
            (call.kwargs['query'], call.kwargs['result_count'])
            for call in fire.call_args_list
            if call.args and call.args[0] == MorpheusEvents.SEARCH_PERFORMED
        ]
        self.assertEqual(searches, [('kayak kotor', 2), ('kayak ulcinj', 0)])


@override_settings(BOOKING_LISTING_MODE=False)
class ShopResultsTests(SearchFixture, TestCase):
    def test_the_shop_searches_its_goods(self):
        self.assertEqual(self._slugs('/shop/?q=honey'), ['wild-honey'])
        self.assertEqual(self._slugs('/shop/?q=med'), ['wild-honey'])
        self.assertEqual(self._slugs('/shop/?q=kayak'), [])
        self.assertEqual(len(self._slugs('/shop/')), 1)


class SearchWordsTests(SimpleTestCase):
    def test_headings(self):
        self.assertEqual(
            search_page.heading(P(q='kayak', region='kotor', region_label='Kotor Bay')),
            '“kayak” in Kotor Bay',
        )
        self.assertEqual(search_page.heading(P(q='kayak')), '“kayak” in Montenegro')
        self.assertEqual(
            search_page.heading(P(category=WATER)), 'Water Sports experiences in Montenegro'
        )
        self.assertEqual(
            search_page.heading(P(category=WATER, region='budva', region_label='Budva Riviera')),
            'Water Sports experiences in Budva Riviera',
        )
        self.assertEqual(search_page.heading(P()), 'Experiences in Montenegro')
        self.assertEqual(
            search_page.heading(P(q='kayak', day=SUNDAY)), '“kayak” in Montenegro on Sun 18 Oct'
        )

    def test_the_empty_state(self):
        self.assertEqual(
            search_page.empty_message(P(q='zzz', day=SUNDAY)),
            'No experiences match “zzz” on Sun 18 Oct',
        )
        self.assertEqual(search_page.empty_message(P(q='zzz')), 'No experiences match “zzz”')
        self.assertEqual(
            search_page.empty_message(P(day=SUNDAY)), 'Nothing left to book on Sun 18 Oct'
        )
        self.assertEqual(search_page.empty_message(P()), 'No experiences match your search.')
        self.assertEqual(
            search_page.empty_message(P(q='x'), kind='product'), 'No products match “x”'
        )

    def test_dates_are_latin_in_serbian(self):
        self.assertEqual(search_page.date_label(SUNDAY), 'Sun 18 Oct')
        self.assertEqual(search_page.date_label(None), '')
        with translation.override('sr'):
            self.assertEqual(search_page.date_label(SUNDAY), 'ned 18. okt')
            self.assertEqual(search_page.date_locale(), ('sr_Latn_ME', 'sr-Latn-ME'))

    def test_serbian_words(self):
        with translation.override('sr'):
            self.assertEqual(search_page.heading(P(q='kajak')), '„kajak“ u Crnoj Gori')
            self.assertEqual(
                search_page.heading(P(q='kajak', day=SUNDAY)), '„kajak“ u Crnoj Gori, ned 18. okt'
            )
            self.assertEqual(
                search_page.heading(P(q='kajak', region='kotor', region_label='Boka Kotorska')),
                '„kajak“ — Boka Kotorska',
            )
            self.assertEqual(
                search_page.empty_message(P(q='kajak')),
                'Nijedan doživljaj ne odgovara upitu „kajak“',
            )
            self.assertEqual(
                search_page.empty_message(P(day=SUNDAY)), 'Za ned 18. okt nema slobodnih mjesta'
            )
