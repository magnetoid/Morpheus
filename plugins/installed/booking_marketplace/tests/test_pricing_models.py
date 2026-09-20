from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import AddOn, BookableService, PricingTier


def _svc():
    from plugins.installed.catalog.models import Vendor

    v = Vendor.objects.create(name='V', slug='v', is_active=True)
    return BookableService.objects.create(vendor=v, name='K', slug='k', price=Money(50, 'EUR'))


class PricingModelTests(TestCase):
    def test_tier_and_addon_relations(self):
        svc = _svc()
        PricingTier.objects.create(service=svc, name='Adult', price=Money(50, 'EUR'), min_qty=1)
        PricingTier.objects.create(service=svc, name='Child', price=Money(25, 'EUR'))
        AddOn.objects.create(
            service=svc, name='Pickup', price=Money(10, 'EUR'), price_type='per_booking'
        )
        self.assertEqual(svc.tiers.count(), 2)
        self.assertEqual(svc.addons.first().price_type, 'per_booking')
        self.assertEqual(svc.tiers.get(name='Adult').price, Money(50, 'EUR'))
