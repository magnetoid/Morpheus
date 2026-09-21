"""Hotel meta descriptions must be unique, in-range, and honest.

The generated `short_description` (the hotel page's meta description) was
tier + type + town only, so nine 4-star Podgorica hotels published
'An upscale hotel in Podgorica.' — the audit's top warning (18 groups,
52 hotels). It is now led by the unique hotel name and names the hotel's
real amenities.
"""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from plugins.installed.booking_marketplace.management.commands.seed_hotels_montenegro import (
    _blurb_for,
    _feature_phrase,
    _legacy_short_blurb,
)
from plugins.installed.booking_marketplace.models import Property
from plugins.installed.catalog.models import Vendor


class BlurbGeneratorTests(TestCase):
    def test_same_class_hotels_get_distinct_descriptions(self):
        """Two 4-star Podgorica hotels — identical everything but the name —
        no longer collide, because the name leads the blurb."""
        a = _blurb_for('Hotel Podgorica', 'Podgorica', 4, 'Hotel', ['wifi', 'parking'])[0]
        b = _blurb_for('Hotel Crna Gora', 'Podgorica', 4, 'Hotel', ['wifi', 'parking'])[0]
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith('Hotel Podgorica is '))
        self.assertTrue(b.startswith('Hotel Crna Gora is '))

    def test_only_real_amenities_are_named(self):
        """The blurb is a public claim — it must not invent a spa. A hotel
        with wifi/parking never has 'spa', 'pool' or 'sea views' in its blurb."""
        short = _blurb_for('Hotel X', 'Nikšić', 3, 'Hotel', ['wifi', 'parking'])[0]
        for absent in ('spa', 'pool', 'sea views', 'beachfront'):
            self.assertNotIn(absent, short)
        self.assertIn('free WiFi', short)

    def test_at_most_three_features_named(self):
        short = _blurb_for(
            'Aman',
            'Sveti Stefan',
            5,
            'Resort',
            ['sea_view', 'beachfront', 'spa', 'pool', 'restaurant', 'gym', 'wifi'],
        )[0]
        # priority order: sea_view, beachfront, spa are the first three
        self.assertIn('sea views, a beachfront and a spa', short)
        self.assertNotIn('pool', short)

    def test_no_features_falls_back_to_a_clean_sentence(self):
        short = _blurb_for('Sparse Inn', 'Žabljak', 2, 'Guesthouse', [])[0]
        self.assertEqual(
            short, 'Sparse Inn is a simple, comfortable 2-star guesthouse in Žabljak, Montenegro.'
        )

    def test_typical_blurb_lands_in_the_meta_length_window(self):
        short = _blurb_for(
            'Hotel Podgorica', 'Podgorica', 4, 'Hotel', ['wifi', 'parking', 'restaurant']
        )[0]
        self.assertGreaterEqual(len(short), 70)
        self.assertLessEqual(len(short), 160)

    def test_feature_phrase_joins_naturally(self):
        self.assertEqual(_feature_phrase(['wifi']), 'free WiFi')
        self.assertEqual(_feature_phrase(['spa', 'pool']), 'a spa and a pool')
        self.assertEqual(
            _feature_phrase(['sea_view', 'spa', 'pool']), 'sea views, a spa and a pool'
        )
        self.assertEqual(_feature_phrase([]), '')


class RefreshCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vendor = Vendor.objects.create(name='Stays', slug='stays', is_active=True)

    def _hotel(self, name, town, star, ptype, ptype_label, amenities, short):
        return Property.objects.create(
            vendor=self.vendor,
            name=name,
            slug=name.lower().replace(' ', '-'),
            property_type=ptype,
            star_rating=star,
            location=town,
            amenities=amenities,
            short_description=short,
        )

    def test_legacy_rows_are_rewritten_edited_rows_are_kept(self):
        legacy = _legacy_short_blurb('Podgorica', 4, 'Hotel')
        generated = self._hotel(
            'Hotel A', 'Podgorica', 4, 'hotel', 'Hotel', ['wifi', 'parking'], legacy
        )
        edited = self._hotel(
            'Hotel B',
            'Podgorica',
            4,
            'hotel',
            'Hotel',
            ['wifi'],
            'Our family-run hotel by the park.',
        )

        call_command('refresh_hotel_blurbs', stdout=StringIO())
        generated.refresh_from_db()
        edited.refresh_from_db()

        self.assertTrue(generated.short_description.startswith('Hotel A is '))
        self.assertNotEqual(generated.short_description, legacy)
        # a host's own words survive
        self.assertEqual(edited.short_description, 'Our family-run hotel by the park.')

    def test_second_run_changes_nothing(self):
        self._hotel(
            'Hotel A',
            'Podgorica',
            4,
            'hotel',
            'Hotel',
            ['wifi'],
            _legacy_short_blurb('Podgorica', 4, 'Hotel'),
        )
        call_command('refresh_hotel_blurbs', stdout=StringIO())
        after_first = Property.objects.get(name='Hotel A').short_description
        out = StringIO()
        call_command('refresh_hotel_blurbs', stdout=out)
        self.assertEqual(Property.objects.get(name='Hotel A').short_description, after_first)
        self.assertIn('rewrote 0', out.getvalue())

    def test_dry_run_writes_nothing(self):
        legacy = _legacy_short_blurb('Podgorica', 4, 'Hotel')
        self._hotel('Hotel A', 'Podgorica', 4, 'hotel', 'Hotel', ['wifi'], legacy)
        call_command('refresh_hotel_blurbs', '--dry-run', stdout=StringIO())
        self.assertEqual(Property.objects.get(name='Hotel A').short_description, legacy)
