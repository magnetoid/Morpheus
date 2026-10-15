"""The store's search index follows its listings (booking_marketplace/search.py).

The index lives in each web process. A listing, place or category saved or deleted
anywhere bumps a version token in the shared cache, and every process rebuilds before
its next search; an edit that skips save() (QuerySet.update() in the seed commands) is
picked up once the index is MAX_AGE_S old.
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace import search
from plugins.installed.booking_marketplace.models import BookableService, Place
from plugins.installed.catalog.models import Category, Vendor


class StoreIndexTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        self.water = Category.objects.create(name='Water Sports', slug='water-sports')
        self.kayak = BookableService.objects.create(
            vendor=self.vendor,
            name='Sunset Kayak Tour',
            slug='sunset-kayak',
            location='Herceg Novi',
            region='kotor',
            category=self.water,
            highlights=['Glass-bottom view of the reef'],
            short_description='<p>Paddle under the walls.</p>',
            description='Ends with grilled sardines.',
            price=Money(50, 'EUR'),
        )

    def _found(self, q, kind='experience'):
        found = search.listing_index().find(search.parse_query(q), kind=kind)
        return set(found.scores) if found else set()

    def test_every_field_a_visitor_types(self):
        # name, location, region (English and Serbian), category, highlights, summary, text
        for q in ('sunset', 'herceg', 'kotor bay', 'boka', 'water', 'glass', 'paddle', 'sardines'):
            with self.subTest(q=q):
                self.assertEqual(self._found(q), {self.kayak.pk})

    def test_a_rename_reaches_the_next_search(self):
        self.assertEqual(self._found('sunset'), {self.kayak.pk})
        self.kayak.name = 'Morning Kayak Tour'
        self.kayak.save()
        self.assertEqual(self._found('sunset'), set())
        self.assertEqual(self._found('morning'), {self.kayak.pk})

    def test_a_deactivated_or_deleted_listing_leaves(self):
        self.kayak.is_active = False
        self.kayak.save()
        self.assertEqual(self._found('sunset'), set())
        self.kayak.is_active = True
        self.kayak.save()
        self.assertEqual(self._found('sunset'), {self.kayak.pk})
        self.kayak.delete()
        self.assertEqual(self._found('sunset'), set())

    def test_a_category_rename_reaches_the_next_search(self):
        self.assertEqual(self._found('water'), {self.kayak.pk})
        self.water.name = 'Paddling'
        self.water.save()
        self.assertEqual(self._found('water'), set())
        self.assertEqual(self._found('paddling'), {self.kayak.pk})

    def test_places_are_indexed(self):
        place = Place.objects.create(
            name='Perast',
            slug='perast',
            region='kotor',
            is_active=True,
            summary='s',
            description='d',
        )
        self.assertEqual(self._found('perast', kind='place'), {place.pk})
        self.assertEqual(self._found('perast'), set())

    def test_another_process_bump_rebuilds(self):
        search.listing_index()
        BookableService.objects.filter(pk=self.kayak.pk).update(name='Dawn Kayak Tour')
        self.assertEqual(self._found('dawn'), set())  # this process still has the old index
        cache.set(search._VERSION_KEY, 'set-by-another-process')
        self.assertEqual(self._found('dawn'), {self.kayak.pk})

    def test_a_lost_version_key_rebuilds(self):
        search.listing_index()
        BookableService.objects.filter(pk=self.kayak.pk).update(name='Dawn Kayak Tour')
        cache.delete(search._VERSION_KEY)
        self.assertEqual(self._found('dawn'), {self.kayak.pk})

    def test_an_edit_that_skips_save_is_found_once_the_index_ages_out(self):
        search.listing_index()
        BookableService.objects.filter(pk=self.kayak.pk).update(name='Dawn Kayak Tour')
        self.assertEqual(self._found('dawn'), set())
        version, built_at, index = search._STATE['built']
        search._STATE['built'] = (version, built_at - search.MAX_AGE_S - 1, index)
        self.assertEqual(self._found('dawn'), {self.kayak.pk})
