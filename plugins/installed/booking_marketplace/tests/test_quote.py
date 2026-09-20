import datetime

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace import services as S
from plugins.installed.booking_marketplace.models import AddOn, BookableService, PricingTier


def _svc(price=50):
    from plugins.installed.catalog.models import Vendor

    v = Vendor.objects.create(name='V', slug='v', is_active=True)
    return BookableService.objects.create(vendor=v, name='K', slug='k', price=Money(price, 'EUR'))


class QuoteTests(TestCase):
    def test_flat_price_fallback(self):
        svc = _svc(50)
        q = S.price_quote(svc, tiers={'guests': 3}, addons={})
        self.assertEqual(q['subtotal'], Money(150, 'EUR'))
        self.assertEqual(q['fee'], Money(18, 'EUR'))
        self.assertEqual(q['total'], Money(168, 'EUR'))
        self.assertEqual(q['guests'], 3)

    def test_tiers_and_addons(self):
        svc = _svc(50)
        adult = PricingTier.objects.create(service=svc, name='Adult', price=Money(50, 'EUR'))
        child = PricingTier.objects.create(service=svc, name='Child', price=Money(25, 'EUR'))
        pickup = AddOn.objects.create(
            service=svc, name='Pickup', price=Money(10, 'EUR'), price_type='per_booking'
        )
        photos = AddOn.objects.create(
            service=svc, name='Photos', price=Money(5, 'EUR'), price_type='per_person'
        )
        q = S.price_quote(
            svc,
            tiers={str(adult.id): 2, str(child.id): 1},  # 100 + 25 = 125
            addons={str(pickup.id): 1, str(photos.id): 1},  # 10 + 5*3 = 25
        )
        self.assertEqual(q['guests'], 3)
        self.assertEqual(q['subtotal'], Money(150, 'EUR'))  # 125 + 25
        self.assertEqual(q['total'], Money(168, 'EUR'))  # +12% fee = 18

    def test_unknown_tier_rejected(self):
        svc = _svc()
        PricingTier.objects.create(service=svc, name='Adult', price=Money(50, 'EUR'))
        with self.assertRaises(S.BookingError):
            S.price_quote(svc, tiers={'00000000-0000-0000-0000-000000000000': 1}, addons={})


class BookingWithTiersTests(TestCase):
    def _future(self):
        return timezone.localdate() + datetime.timedelta(days=2)

    def test_create_booking_with_tiers_snapshots(self):
        svc = _svc(50)
        adult = PricingTier.objects.create(service=svc, name='Adult', price=Money(50, 'EUR'))
        b = S.create_booking(
            svc,
            booking_date=self._future(),
            guests=0,
            name='A',
            email='a@x.io',
            tiers={str(adult.id): 2},
            time='09:00',
        )
        self.assertEqual(b.total_price, Money(112, 'EUR'))  # 100 + 12%
        self.assertEqual(b.tier_breakdown[0]['name'], 'Adult')
        self.assertEqual(b.time_slot, '09:00')

    def test_enquiry_captures_selection(self):
        svc = _svc(50)
        adult = PricingTier.objects.create(service=svc, name='Adult', price=Money(50, 'EUR'))
        e = S.submit_enquiry(
            svc,
            email='lead@x.io',
            name='Lead',
            tiers={str(adult.id): 3},
            time='14:30',
            preferred_date=self._future(),
        )
        self.assertEqual(e.time_slot, '14:30')
        self.assertEqual(e.tier_breakdown[0]['qty'], 3)
