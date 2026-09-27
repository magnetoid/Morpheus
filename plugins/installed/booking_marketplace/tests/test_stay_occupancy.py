"""A room's adult limit is part of its occupancy rule, not decoration.

Every seeded Montenegro room type carries `max_adults` below `max_occupancy`
(e.g. a double: 2 adults + 1 child = 3). `quote_stay` enforced the total and the
children, never the adults — so three adults were quoted, and could be booked,
into a room the hotel sells for two.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace import stays
from plugins.installed.booking_marketplace.models import Property, RoomType
from plugins.installed.booking_marketplace.services import BookingError


def _future(days):
    return timezone.localdate() + datetime.timedelta(days=days)


class StayAdultLimitTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Vendor

        vendor = Vendor.objects.create(name='Occupancy Hotels', slug='occupancy-hotels')
        prop = Property.objects.create(vendor=vendor, name='Hotel Budva', slug='hotel-budva-occ')
        self.room = RoomType.objects.create(
            property=prop,
            name='Double with extra bed',
            slug='double-extra-bed',
            base_rate=Money(Decimal('100.00'), 'EUR'),
            max_occupancy=3,
            max_adults=2,
            max_children=1,
            room_count=4,
        )

    def _quote(self, rooms, adults, children):
        return stays.quote_stay(
            self.room,
            check_in=_future(10),
            check_out=_future(12),
            rooms=rooms,
            adults=adults,
            children=children,
        )

    def test_three_adults_do_not_fit_a_two_adult_room(self):
        with self.assertRaises(BookingError):
            self._quote(rooms=1, adults=3, children=0)

    def test_the_rooms_real_mix_still_quotes(self):
        self.assertEqual(self._quote(rooms=1, adults=2, children=1)['guests'], 3)
        self.assertEqual(self._quote(rooms=2, adults=4, children=2)['guests'], 6)
