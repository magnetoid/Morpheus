"""Shipping, returns and availability: only what is true, and only from its owner.

Structured data is a set of public claims about money and delivery. Google
reconciles them against the page and the Merchant Center feed, and a shopper
reads them in the result. Until v0.48 the SEO app assembled all three itself
from configuration nothing wrote, so every store on the platform published the
same invented policy — most damagingly **free shipping on everything**, because
the threshold defaulted to the truthy string `'0'`.

So these tests assert two directions, and the second matters more:

* when an owner app HAS the data, the claim appears and matches it;
* when it does NOT, the claim is absent — never defaulted, never guessed.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from core.seo_page import KIND_PRODUCT, SeoPage
from plugins.installed.catalog.models import Product
from plugins.installed.seo.schema import build_graph


def _offer(graph) -> dict:
    for node in (graph or {}).get('@graph', []):
        if 'Product' in str(node.get('@type', '')):
            return node.get('offers') or {}
    return {}


class OfferClaimTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Claims Probe',
            slug='claims-probe',
            sku='CL-1',
            status='active',
            price=Money(Decimal('30.00'), 'USD'),
        )

    def _graph(self):
        return build_graph(
            SeoPage(
                kind=KIND_PRODUCT,
                obj=self.product,
                rendered={
                    'slug': 'claims-probe',
                    'name': 'Claims Probe',
                    'price': {'amount': '30.00', 'currency': 'USD'},
                },
                path='/products/claims-probe/',
                title='Claims Probe',
            )
        )

    # -- absence ---------------------------------------------------------
    def test_no_shipping_rates_means_no_shipping_claim(self):
        """The headline bug. With nothing configured the page said free
        shipping to the US; now it says nothing about shipping at all."""
        offer = self._offer_now()
        self.assertNotIn('shippingDetails', offer)

    def test_no_store_country_means_no_return_policy_claim(self):
        """`applicableCountry` is required on a MerchantReturnPolicy, so a
        policy without one is invalid — and naming the wrong country is worse
        than staying quiet."""
        offer = self._offer_now()
        self.assertNotIn('hasMerchantReturnPolicy', offer)

    def _offer_now(self):
        return _offer(self._graph())

    # -- presence --------------------------------------------------------
    def test_a_configured_rate_is_published_at_its_real_price(self):
        from plugins.installed.shipping.models import ShippingRate, ShippingZone

        zone = ShippingZone.objects.create(name='Home', countries=['GB'])
        ShippingRate.objects.create(
            zone=zone,
            name='Standard',
            computation='flat',
            flat_amount=Money(Decimal('4.95'), 'GBP'),
            estimated_days_min=2,
            estimated_days_max=4,
        )

        details = self._offer_now().get('shippingDetails') or {}

        self.assertEqual(details.get('shippingRate', {}).get('value'), '4.95')
        self.assertEqual(details.get('shippingDestination', {}).get('addressCountry'), 'GB')
        self.assertEqual(details.get('deliveryTime', {}).get('transitTime', {}).get('maxValue'), 4)
        # Handling time is a warehouse fact no app holds; the old code invented
        # "0–1 days" for every store.
        self.assertNotIn('handlingTime', details.get('deliveryTime', {}))

    def test_a_carrier_quoted_rate_publishes_no_price(self):
        """A live carrier rate is only known at checkout. Quoting a number for
        it would be a guess presented as a fact."""
        from plugins.installed.shipping.models import ShippingRate, ShippingZone

        zone = ShippingZone.objects.create(name='Carrier', countries=['US'])
        ShippingRate.objects.create(zone=zone, name='Live', computation='carrier_shippo')

        self.assertNotIn('shippingDetails', self._offer_now())

    def test_the_return_window_is_published_once_the_store_has_a_country(self):
        from core.models import StoreSettings

        StoreSettings.objects.create(store_name='Claims Test', country='GB')

        policy = self._offer_now().get('hasMerchantReturnPolicy') or {}

        self.assertEqual(policy.get('applicableCountry'), 'GB')
        self.assertEqual(policy.get('merchantReturnDays'), 30)
        # Who pays for the return is not something this platform knows.
        self.assertNotIn('returnFees', policy)
        self.assertNotIn('returnMethod', policy)


class AvailabilityTests(TestCase):
    """One vocabulary, and it has to reflect the warehouse."""

    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Stock Probe',
            slug='stock-probe',
            sku='ST-1',
            status='active',
            price=Money(Decimal('11.00'), 'USD'),
        )

    def test_a_product_with_no_stock_rows_is_purchasable(self):
        """No inventory tracking means nothing is holding the sale back."""
        from plugins.installed.inventory.services import product_availability

        self.assertEqual(product_availability(self.product), 'in_stock')

    def test_variants_with_no_stock_rows_are_untracked_not_sold_out(self):
        """The bug this shipped with. A store that has never created a single
        StockLevel row aggregates to zero for every variant — and the first
        version read that as sold out, so every product page on a shop with
        inventory tracking switched off declared OutOfStock while its add-to-cart
        button worked. Absence of measurement is not a measurement of absence."""
        from plugins.installed.catalog.models import ProductVariant
        from plugins.installed.inventory.services import product_availability

        ProductVariant.objects.create(
            product=self.product, name='Print', sku='ST-1-N', inventory_policy='deny'
        )
        self.assertEqual(product_availability(self.product), 'in_stock')

    def test_an_untracked_variant_keeps_the_product_buyable(self):
        """One counted variant at zero must not bury a sibling nobody counts."""
        from plugins.installed.catalog.models import ProductVariant
        from plugins.installed.inventory.models import StockLevel, Warehouse
        from plugins.installed.inventory.services import product_availability

        counted = ProductVariant.objects.create(
            product=self.product, name='Counted', sku='ST-1-D', inventory_policy='deny'
        )
        ProductVariant.objects.create(
            product=self.product, name='Untracked', sku='ST-1-E', inventory_policy='deny'
        )
        warehouse = Warehouse.objects.create(name='Main', code='MAIN')
        StockLevel.objects.create(variant=counted, warehouse=warehouse, quantity=0)

        self.assertEqual(product_availability(self.product), 'in_stock')

    def test_a_product_that_does_not_track_inventory_is_always_purchasable(self):
        """`track_inventory=False` is the merchant saying so in as many words."""
        from plugins.installed.catalog.models import ProductVariant
        from plugins.installed.inventory.models import StockLevel, Warehouse
        from plugins.installed.inventory.services import product_availability

        self.product.track_inventory = False
        self.product.save(update_fields=['track_inventory'])
        variant = ProductVariant.objects.create(
            product=self.product, name='Zeroed', sku='ST-1-F', inventory_policy='deny'
        )
        warehouse = Warehouse.objects.create(name='Main', code='MAIN')
        StockLevel.objects.create(variant=variant, warehouse=warehouse, quantity=0)

        self.assertEqual(product_availability(self.product), 'in_stock')

    def test_a_variant_with_zero_stock_is_out_of_stock(self):
        """The check that never ran on a product page: it lived behind an
        ORM-only branch, so the page always said InStock."""
        from plugins.installed.catalog.models import ProductVariant
        from plugins.installed.inventory.models import StockLevel, Warehouse
        from plugins.installed.inventory.services import product_availability

        variant = ProductVariant.objects.create(
            product=self.product, name='Only', sku='ST-1-A', inventory_policy='deny'
        )
        warehouse = Warehouse.objects.create(name='Main', code='MAIN')
        StockLevel.objects.create(variant=variant, warehouse=warehouse, quantity=0)

        self.assertEqual(product_availability(self.product), 'out_of_stock')

    def test_a_backorder_variant_is_still_buyable(self):
        from plugins.installed.catalog.models import ProductVariant
        from plugins.installed.inventory.models import StockLevel, Warehouse
        from plugins.installed.inventory.services import product_availability

        variant = ProductVariant.objects.create(
            product=self.product, name='Backordered', sku='ST-1-B', inventory_policy='continue'
        )
        warehouse = Warehouse.objects.create(name='Main', code='MAIN')
        StockLevel.objects.create(variant=variant, warehouse=warehouse, quantity=0)

        self.assertEqual(product_availability(self.product), 'backorder')

    def test_an_archived_product_is_discontinued(self):
        from plugins.installed.inventory.services import product_availability

        self.product.status = 'archived'
        self.assertEqual(product_availability(self.product), 'discontinued')

    def test_the_markup_repeats_whatever_the_warehouse_says(self):
        """The whole point of one vocabulary: feed, Open Graph and JSON-LD
        cannot disagree about the same item."""
        from plugins.feed_mapping import availability_to_schema
        from plugins.installed.catalog.models import ProductVariant
        from plugins.installed.inventory.models import StockLevel, Warehouse

        variant = ProductVariant.objects.create(
            product=self.product, name='Only', sku='ST-1-C', inventory_policy='deny'
        )
        warehouse = Warehouse.objects.create(name='Main', code='MAIN')
        StockLevel.objects.create(variant=variant, warehouse=warehouse, quantity=0)

        self.assertEqual(availability_to_schema(self.product), 'https://schema.org/OutOfStock')
