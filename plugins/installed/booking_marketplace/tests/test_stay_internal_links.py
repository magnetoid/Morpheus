"""A hotel page links out to its region — nearby destination guides and
sibling hotels — and renders its stay policies.

The page previously ended at the room list with two generic links; these
blocks give crawlers the region hub<->spoke the audit asked for, and surface
the `policies` field that was stored but never rendered.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from plugins.installed.booking_marketplace import stays
from plugins.installed.booking_marketplace.models import Place, Property
from plugins.installed.booking_marketplace.stay_views import _policies
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Vendor


class RelatedStaysServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vendor = Vendor.objects.create(name='Stays', slug='stays', is_active=True)
        cls.hotel = cls._hotel('Hotel Base', 'Budva', 'budva', 4)
        cls.same_town = cls._hotel('Hotel Budva Two', 'Budva', 'budva', 5)
        cls.same_region = cls._hotel('Hotel Bečići', 'Bečići', 'budva', 3)
        cls.other_region = cls._hotel('Hotel Kotor', 'Kotor', 'kotor', 5)

    @classmethod
    def _hotel(cls, name, town, region, star, **kw):
        kw.setdefault('vendor', cls.vendor)
        return Property.objects.create(
            name=name,
            slug=name.lower().replace(' ', '-').replace('č', 'c').replace('ć', 'c'),
            property_type='hotel',
            star_rating=star,
            location=town,
            region=region,
            price_from=Decimal('90.00'),
            **kw,
        )

    def test_related_excludes_self_and_other_regions(self):
        related = stays.related_stays(self.hotel)
        pks = {p.pk for p in related}
        self.assertNotIn(self.hotel.pk, pks)
        self.assertNotIn(self.other_region.pk, pks)
        self.assertIn(self.same_town.pk, pks)
        self.assertIn(self.same_region.pk, pks)

    def test_same_town_comes_before_the_wider_region(self):
        related = stays.related_stays(self.hotel)
        self.assertEqual(related[0].pk, self.same_town.pk)  # same town, ranked first

    def test_inactive_hotel_and_inactive_vendor_are_excluded(self):
        Property.objects.filter(pk=self.same_region.pk).update(is_active=False)
        dead_vendor = Vendor.objects.create(name='Gone', slug='gone', is_active=False)
        self._hotel('Hotel Ghost', 'Budva', 'budva', 5, vendor=dead_vendor)
        pks = {p.pk for p in stays.related_stays(self.hotel)}
        self.assertNotIn(self.same_region.pk, pks)
        self.assertFalse(any(p.name == 'Hotel Ghost' for p in stays.related_stays(self.hotel)))

    def test_limit_is_honoured(self):
        for i in range(8):
            self._hotel(f'Extra {i}', 'Budva', 'budva', 3)
        self.assertLessEqual(len(stays.related_stays(self.hotel, limit=6)), 6)


class NearbyPlacesServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vendor = Vendor.objects.create(name='Stays', slug='stays', is_active=True)
        cls.hotel = Property.objects.create(
            vendor=cls.vendor,
            name='Hotel Base',
            slug='hotel-base',
            property_type='hotel',
            star_rating=4,
            location='Budva',
            region='budva',
        )
        cls.place = Place.objects.create(name='Sveti Stefan', slug='sveti-stefan', region='budva')
        Place.objects.create(name='Kotor Old Town', slug='kotor-old-town', region='kotor')

    def test_returns_only_places_in_the_hotels_region(self):
        places = stays.nearby_places(self.hotel)
        self.assertEqual([p.slug for p in places], ['sveti-stefan'])

    def test_inactive_place_excluded(self):
        Place.objects.filter(pk=self.place.pk).update(is_active=False)
        self.assertEqual(stays.nearby_places(self.hotel), [])

    def test_regionless_hotel_gets_nothing(self):
        Property.objects.filter(pk=self.hotel.pk).update(region='')
        self.hotel.refresh_from_db()
        self.assertEqual(stays.nearby_places(self.hotel), [])


class StayDetailRendersLinksTests(MontenegroThemeMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vendor = Vendor.objects.create(name='Stays', slug='stays', is_active=True)
        cls.hotel = Property.objects.create(
            vendor=cls.vendor,
            name='Hotel Base',
            slug='hotel-base',
            property_type='hotel',
            star_rating=4,
            location='Budva',
            region='budva',
            short_description='A comfortable base in Budva.',
            policies={'cancellation': 'Free cancellation up to 3 days before check-in.'},
        )
        cls.sibling = Property.objects.create(
            vendor=cls.vendor,
            name='Hotel Neighbour',
            slug='hotel-neighbour',
            property_type='hotel',
            star_rating=5,
            location='Budva',
            region='budva',
        )
        cls.place = Place.objects.create(
            name='Sveti Stefan',
            slug='sveti-stefan',
            region='budva',
            summary='An islet resort off the Budva Riviera.',
        )

    def test_page_links_to_sibling_hotel_and_nearby_place(self):
        resp = self.client.get('/hotels/hotel-base/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # unique markers (slugs), never a bare display word — the theme's own
        # copy contains 'Budva' many times over.
        self.assertIn('/hotels/hotel-neighbour/', html)
        self.assertIn('/places/sveti-stefan/', html)

    def test_page_renders_the_cancellation_policy(self):
        resp = self.client.get('/hotels/hotel-base/')
        self.assertIn('Free cancellation up to 3 days before check-in.', resp.content.decode())

    def test_page_does_not_link_to_itself(self):
        html = self.client.get('/hotels/hotel-base/').content.decode()
        # the self link only appears in the breadcrumb's current crumb (plain text),
        # never as an <a href> in the related-stays rail
        self.assertNotIn('href="/hotels/hotel-base/"', html)


class PolicyResolutionTests(TestCase):
    """The policies dict shape lives in the plugin (POLICY_LABELS + _policies),
    never hardcoded in the theme — so a new policy key renders with no theme
    edit, mirroring how amenities work."""

    def test_canonical_order_regardless_of_stored_order(self):
        items = _policies({'payment': 'Cards', 'cancellation': 'Free', 'pets': 'No pets'})
        self.assertEqual([i['key'] for i in items], ['cancellation', 'pets', 'payment'])

    def test_empty_and_missing_values_are_skipped(self):
        items = _policies({'cancellation': 'Free', 'children': '', 'pets': '   '})
        self.assertEqual([i['key'] for i in items], ['cancellation'])

    def test_unknown_key_is_humanised_and_kept(self):
        items = _policies({'smoking_policy': 'No smoking indoors.'})
        self.assertEqual(
            items,
            [{'key': 'smoking_policy', 'label': 'Smoking policy', 'value': 'No smoking indoors.'}],
        )

    def test_none_is_safe(self):
        self.assertEqual(_policies(None), [])


class PolicyRenderIsDataDrivenTests(MontenegroThemeMixin, TestCase):
    def test_a_policy_key_the_theme_never_names_still_renders(self):
        """Proof the theme is not hardcoded to the four seeded keys: an
        unrecognised key reaches the page through _policies alone."""
        vendor = Vendor.objects.create(name='Stays', slug='stays', is_active=True)
        Property.objects.create(
            vendor=vendor,
            name='Hotel Base',
            slug='hotel-base',
            property_type='hotel',
            star_rating=4,
            location='Budva',
            region='budva',
            policies={'smoking_policy': 'No smoking indoors.'},
        )
        html = self.client.get('/hotels/hotel-base/').content.decode()
        self.assertIn('Smoking policy', html)
        self.assertIn('No smoking indoors.', html)
