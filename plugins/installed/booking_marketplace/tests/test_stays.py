"""Accommodation (stays) engine — models, pricing, availability, booking, enquiry."""

import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money


def _future(days):
    return timezone.localdate() + datetime.timedelta(days=days)


class StayModelTests(TestCase):
    def _property(self):
        from plugins.installed.catalog.models import Vendor
        from plugins.installed.booking_marketplace.models import Property, RoomType

        vendor = Vendor.objects.create(name='Adriatic Hotels', slug='adriatic-hotels')
        prop = Property.objects.create(
            vendor=vendor, name='Hotel Kotor Bay', slug='hotel-kotor-bay',
            property_type='hotel', star_rating=4, region='kotor', location='Kotor',
            amenities=['pool', 'spa', 'wifi'], price_from=Money(Decimal('100.00'), 'EUR'),
        )
        room = RoomType.objects.create(
            property=prop, name='Deluxe Double', slug='deluxe-double',
            max_occupancy=3, max_adults=2, max_children=1,
            base_rate=Money(Decimal('120.00'), 'EUR'), room_count=5,
        )
        return prop, room

    def test_property_and_roomtype_persist(self):
        prop, room = self._property()
        self.assertEqual(prop.room_types.count(), 1)
        self.assertEqual(room.property, prop)
        self.assertEqual(prop.vendor.name, 'Adriatic Hotels')
        self.assertEqual(room.base_rate, Money(Decimal('120.00'), 'EUR'))
        self.assertIn('pool', prop.amenities)

    def test_amenity_labels_cover_seeded_slugs(self):
        from plugins.installed.booking_marketplace.models import AMENITY_LABELS
        for slug in ('pool', 'spa', 'wifi', 'airport_shuttle', 'sea_view'):
            self.assertIn(slug, AMENITY_LABELS)


class QuoteStayTests(TestCase):
    def _room(self, rate='120.00', max_occ=3, max_children=1):
        from plugins.installed.catalog.models import Vendor
        from plugins.installed.booking_marketplace.models import Property, RoomType
        v = Vendor.objects.create(name='V', slug='v-quote')
        p = Property.objects.create(vendor=v, name='P', slug='p-quote', region='budva')
        return RoomType.objects.create(
            property=p, name='Std', slug='std', base_rate=Money(Decimal(rate), 'EUR'),
            max_occupancy=max_occ, max_adults=2, max_children=max_children, room_count=3,
        )

    def test_nights_between_math_and_guards(self):
        from plugins.installed.booking_marketplace import stays
        from plugins.installed.booking_marketplace.services import BookingError
        self.assertEqual(stays.nights_between(_future(10), _future(13)), 3)
        with self.assertRaises(BookingError):  # check-out before check-in
            stays.nights_between(_future(13), _future(10))
        with self.assertRaises(BookingError):  # same day = 0 nights
            stays.nights_between(_future(10), _future(10))
        with self.assertRaises(BookingError):  # past
            stays.nights_between(_future(-1), _future(2))
        with self.assertRaises(BookingError):  # > 30 nights
            stays.nights_between(_future(1), _future(40))

    def test_quote_math(self):
        from plugins.installed.booking_marketplace import stays
        room = self._room(rate='120.00')
        q = stays.quote_stay(room, check_in=_future(10), check_out=_future(13),
                             rooms=1, adults=2, children=1)
        self.assertEqual(q['nights'], 3)
        self.assertEqual(len(q['nightly']), 3)
        self.assertEqual(q['room_subtotal'], Money(Decimal('360.00'), 'EUR'))   # 120*3*1
        self.assertEqual(q['service_fee'], Money(Decimal('43.20'), 'EUR'))      # 12% of 360
        self.assertEqual(q['tourist_tax'], Money(Decimal('9.00'), 'EUR'))       # 1 * 3 guests * 3 nights
        self.assertEqual(q['total'], Money(Decimal('412.20'), 'EUR'))

    def test_quote_multi_room_subtotal(self):
        from plugins.installed.booking_marketplace import stays
        room = self._room(rate='100.00', max_occ=2)
        q = stays.quote_stay(room, check_in=_future(5), check_out=_future(7),
                             rooms=2, adults=4, children=0)
        self.assertEqual(q['room_subtotal'], Money(Decimal('400.00'), 'EUR'))   # 100*2*2

    def test_quote_rejects_over_occupancy(self):
        from plugins.installed.booking_marketplace import stays
        from plugins.installed.booking_marketplace.services import BookingError
        room = self._room(max_occ=2, max_children=0)
        with self.assertRaises(BookingError):
            stays.quote_stay(room, check_in=_future(5), check_out=_future(6),
                             rooms=1, adults=3, children=0)

    def test_nights_between_boundary_30(self):
        from plugins.installed.booking_marketplace import stays
        from plugins.installed.booking_marketplace.services import BookingError
        self.assertEqual(stays.nights_between(_future(1), _future(31)), 30)  # exactly 30 OK
        with self.assertRaises(BookingError):
            stays.nights_between(_future(1), _future(32))                    # 31 rejected

    def test_multi_room_tourist_tax_scales_with_guests(self):
        from plugins.installed.booking_marketplace import stays
        room = self._room(rate='100.00', max_occ=2)
        q = stays.quote_stay(room, check_in=_future(5), check_out=_future(7),
                             rooms=2, adults=4, children=0)
        self.assertEqual(q['tourist_tax'], Money(Decimal('8.00'), 'EUR'))   # 1 * 4 guests * 2 nights


class RoomAvailabilityTests(TestCase):
    def _room(self, count=2):
        from plugins.installed.catalog.models import Vendor
        from plugins.installed.booking_marketplace.models import Property, RoomType
        v = Vendor.objects.create(name='V', slug='v-avail')
        p = Property.objects.create(vendor=v, name='P', slug='p-avail')
        return RoomType.objects.create(
            property=p, name='Std', slug='std', base_rate=Money(Decimal('80'), 'EUR'),
            max_occupancy=2, max_adults=2, room_count=count,
        )

    def _book(self, room, ci, co, rooms=1, status='confirmed'):
        from plugins.installed.booking_marketplace.models import StayBooking
        return StayBooking.objects.create(
            room_type=room, property=room.property, customer_name='G',
            customer_email='g@example.com', check_in=ci, check_out=co, nights=(co - ci).days,
            rooms=rooms, adults=2, children=0, status=status,
        )

    def test_full_inventory_when_no_bookings(self):
        from plugins.installed.booking_marketplace import stays
        room = self._room(count=2)
        self.assertEqual(stays.room_availability(room, _future(10), _future(12)), 2)

    def test_overlapping_booking_decrements(self):
        from plugins.installed.booking_marketplace import stays
        room = self._room(count=2)
        self._book(room, _future(10), _future(13), rooms=1)      # nights 10,11,12
        # query 11→14 overlaps on 11,12 -> 1 used -> 1 free
        self.assertEqual(stays.room_availability(room, _future(11), _future(14)), 1)

    def test_cancelled_booking_ignored(self):
        from plugins.installed.booking_marketplace import stays
        room = self._room(count=1)
        self._book(room, _future(10), _future(13), rooms=1, status='cancelled')
        self.assertEqual(stays.room_availability(room, _future(10), _future(13)), 1)

    def test_adjacent_stays_do_not_collide(self):
        from plugins.installed.booking_marketplace import stays
        room = self._room(count=1)
        self._book(room, _future(10), _future(12), rooms=1)      # last night = 11
        # check-in on 12 (== previous check-out) is free
        self.assertEqual(stays.room_availability(room, _future(12), _future(14)), 1)

    def test_non_overlapping_range_is_free(self):
        from plugins.installed.booking_marketplace import stays
        room = self._room(count=1)
        self._book(room, _future(10), _future(12), rooms=1)
        self.assertEqual(stays.room_availability(room, _future(20), _future(22)), 1)


class CreateStayBookingTests(TestCase):
    def _room(self, count=1):
        from plugins.installed.catalog.models import Vendor
        from plugins.installed.booking_marketplace.models import Property, RoomType
        v = Vendor.objects.create(name='V', slug='v-book')
        p = Property.objects.create(vendor=v, name='P', slug='p-book')
        return RoomType.objects.create(
            property=p, name='Std', slug='std', base_rate=Money(Decimal('100'), 'EUR'),
            max_occupancy=2, max_adults=2, room_count=count,
        )

    def test_creates_server_derived_snapshot(self):
        from plugins.installed.booking_marketplace import stays
        room = self._room(count=2)
        b = stays.create_stay_booking(
            room_type=room, customer_name='Ana', customer_email='ana@example.com',
            check_in=_future(10), check_out=_future(12), rooms=1, adults=2, children=0,
        )
        self.assertEqual(b.nights, 2)
        self.assertEqual(b.property, room.property)
        self.assertEqual(b.subtotal, Money(Decimal('200.00'), 'EUR'))    # 100*2*1
        self.assertEqual(b.service_fee, Money(Decimal('24.00'), 'EUR'))  # 12%
        self.assertEqual(b.tourist_tax, Money(Decimal('4.00'), 'EUR'))   # 1*2 guests*2 nights
        self.assertEqual(b.total, Money(Decimal('228.00'), 'EUR'))
        self.assertEqual(b.status, 'confirmed')
        self.assertEqual(len(b.nightly_breakdown), 2)

    def test_rejects_oversell(self):
        from plugins.installed.booking_marketplace import stays
        from plugins.installed.booking_marketplace.services import BookingError
        room = self._room(count=1)
        stays.create_stay_booking(
            room_type=room, customer_name='A', customer_email='a@example.com',
            check_in=_future(10), check_out=_future(13), rooms=1, adults=2,
        )
        with self.assertRaises(BookingError):     # only 1 room, taken those nights
            stays.create_stay_booking(
                room_type=room, customer_name='B', customer_email='b@example.com',
                check_in=_future(11), check_out=_future(12), rooms=1, adults=2,
            )

    def test_requires_name_and_email(self):
        from plugins.installed.booking_marketplace import stays
        from plugins.installed.booking_marketplace.services import BookingError
        room = self._room()
        with self.assertRaises(BookingError):
            stays.create_stay_booking(
                room_type=room, customer_name='', customer_email='',
                check_in=_future(10), check_out=_future(11), rooms=1, adults=1,
            )


class SubmitStayEnquiryTests(TestCase):
    def _property(self):
        from plugins.installed.catalog.models import Vendor
        from plugins.installed.booking_marketplace.models import Property
        v = Vendor.objects.create(name='V', slug='v-enq')
        return Property.objects.create(vendor=v, name='P', slug='p-enq')

    def test_creates_lead_anonymously(self):
        from plugins.installed.booking_marketplace import stays
        from plugins.installed.booking_marketplace.models import StayEnquiry
        prop = self._property()
        e = stays.submit_stay_enquiry(
            property=prop, email='lead@example.com', name='Lead',
            check_in=_future(10), check_out=_future(12), rooms=1, adults=2,
        )
        self.assertIsInstance(e, StayEnquiry)
        self.assertEqual(e.property, prop)
        self.assertEqual(e.check_in, _future(10))
        self.assertEqual(StayEnquiry.objects.count(), 1)

    def test_requires_email(self):
        from plugins.installed.booking_marketplace import stays
        from plugins.installed.booking_marketplace.services import BookingError
        prop = self._property()
        with self.assertRaises(BookingError):
            stays.submit_stay_enquiry(property=prop, email='')

    def test_capture_survives_notify_failure(self):
        from plugins.installed.booking_marketplace import stays
        from plugins.installed.booking_marketplace.models import StayEnquiry
        prop = self._property()
        with patch('plugins.installed.booking_marketplace.email.notify_stay_enquiry',
                   side_effect=RuntimeError('smtp down')):
            e = stays.submit_stay_enquiry(property=prop, email='lead@example.com')
        self.assertEqual(StayEnquiry.objects.count(), 1)
        self.assertEqual(e.email, 'lead@example.com')
