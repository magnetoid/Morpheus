"""What an experience's or a room's Offer claims, and only what the store can back.

Until November 2026 every experience was `InStock` (whatever its dates, and when the
store only took enquiries), an unpriced listing was offered at 0, room rates
were EUR whatever their currency, and the travel stores published a 30-day
return window on every page, as if a kayak trip went back by post.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.booking_marketplace import seo_jsonld
from plugins.installed.booking_marketplace.models import BookableService, Property, RoomType
from plugins.installed.catalog.models import Vendor

URL = 'https://x.test/bookings/kayak/'
IN_STOCK = 'https://schema.org/InStock'
OUT_OF_STOCK = 'https://schema.org/OutOfStock'


class ExperienceOfferTests(TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(name='Makers', slug='oc-makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=self.vendor,
            name='Kayak',
            slug='oc-kayak',
            listing_kind='experience',
            price=Money(Decimal('50'), 'EUR'),
            daily_capacity=4,
            is_active=True,
        )

    @override_settings(BOOKING_PAYMENTS_READY=True, BOOKING_LISTING_MODE=False)
    def test_an_open_date_is_in_stock(self):
        offer = seo_jsonld._offer(self.svc, URL)
        self.assertEqual(offer['availability'], IN_STOCK)
        self.assertEqual(offer['price'], '50.00')

    @override_settings(BOOKING_PAYMENTS_READY=True, BOOKING_LISTING_MODE=False)
    def test_no_open_date_is_out_of_stock(self):
        self.svc.daily_capacity = 0
        self.svc.save()
        self.assertEqual(seo_jsonld._offer(self.svc, URL)['availability'], OUT_OF_STOCK)

    @override_settings(BOOKING_PAYMENTS_READY=True, BOOKING_LISTING_MODE=False)
    def test_the_pages_own_dates_decide(self):
        self.assertEqual(
            seo_jsonld._offer(self.svc, URL, sessions=[])['availability'], OUT_OF_STOCK
        )

    @override_settings(BOOKING_PAYMENTS_READY=False, BOOKING_LISTING_MODE=False)
    def test_a_store_that_takes_enquiries_claims_no_availability(self):
        offer = seo_jsonld._offer(self.svc, URL)
        self.assertNotIn('availability', offer)
        self.assertEqual(offer['priceCurrency'], 'EUR')

    @override_settings(BOOKING_PAYMENTS_READY=True, BOOKING_LISTING_MODE=False)
    def test_a_product_listing_claims_no_availability(self):
        self.svc.listing_kind = 'product'
        self.svc.save()
        self.assertNotIn('availability', seo_jsonld._offer(self.svc, URL))

    def test_an_unpriced_listing_offers_nothing(self):
        self.svc.price = Money(Decimal('0'), 'EUR')
        self.svc.save()
        self.assertIsNone(seo_jsonld._offer(self.svc, URL))
        nodes = seo_jsonld.experience_nodes(self.svc, url=URL)
        # No offer and no verified rating: no Product node, and a trip without offers.
        self.assertEqual([n['@type'] for n in nodes], ['TouristTrip'])
        self.assertNotIn('offers', nodes[0])


class RoomOfferTests(TestCase):
    def test_a_room_rate_keeps_its_currency_and_claims_no_availability(self):
        vendor = Vendor.objects.create(name='Hosts', slug='oc-hosts', is_active=True)
        prop = Property.objects.create(vendor=vendor, name='P', slug='oc-p', region='budva')
        RoomType.objects.create(
            property=prop,
            name='Std',
            slug='std',
            base_rate=Money(Decimal('90'), 'USD'),
            max_occupancy=2,
            max_adults=2,
        )
        RoomType.objects.create(
            property=prop,
            name='Free',
            slug='free',
            base_rate=Money(Decimal('0'), 'USD'),
            max_occupancy=2,
            max_adults=2,
        )
        (node,) = seo_jsonld.property_nodes(prop, url='https://x.test/hotels/oc-p/')
        (offer,) = node['makesOffer']
        self.assertEqual(offer['priceCurrency'], 'USD')
        self.assertNotIn('availability', offer)
        self.assertNotIn('€', node.get('priceRange', ''))


class TravelReturnPolicyTests(TestCase):
    """A store that sells only experiences publishes no goods return policy."""

    def test_no_policy_on_an_experience_or_the_store(self):
        from core.models import StoreSettings
        from core.seo_page import KIND_PRODUCT, SeoPage
        from plugins.installed.returns_portal import seo_graph

        StoreSettings.objects.create(store_name='Travel', country='ME')
        vendor = Vendor.objects.create(name='Hosts', slug='oc-hosts2', is_active=True)
        svc = BookableService.objects.create(
            vendor=vendor,
            name='Rafting',
            slug='oc-rafting',
            price=Money(Decimal('55'), 'EUR'),
            is_active=True,
        )
        product = svc.product  # the catalog Product it extends: a service
        graph = {
            '@graph': [
                {'@id': 'https://x.test/#organization', '@type': 'OnlineStore'},
                {'@type': 'Product', 'offers': {'@type': 'Offer', 'price': '55.00'}},
            ]
        }
        seo_graph.on_seo_jsonld_graph(graph, page=SeoPage(kind=KIND_PRODUCT, obj=product or svc))
        store, node = graph['@graph']
        self.assertNotIn('hasMerchantReturnPolicy', store)
        self.assertNotIn('hasMerchantReturnPolicy', node['offers'])
