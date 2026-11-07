"""A variant's offer states the price it is sold at (ProductVariant.effective_price).

The offer read the variant's own column and treated only a missing value as
"use the product's price", while checkout treated 0 the same as missing: ten
printed editions on dotbooks priced 0 were published at 0.00 and sold at the
book's price. A free download is offered at 0, which is what it costs; a 0 on a
variant that ships is the product's price.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.seo.services import product_jsonld


class FreeDownloadOfferTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Offer Probe',
            slug='offer-probe',
            sku='OP-1',
            status='active',
            product_type='variable',
            price=Money(Decimal('16.00'), 'USD'),
        )
        ProductVariant.objects.create(
            product=cls.product,
            name='Print',
            sku='OP-1-P',
            variant_type='physical',
            price=Money(0, 'USD'),
        )
        ProductVariant.objects.create(
            product=cls.product,
            name='Digital PDF',
            sku='OP-1-D',
            variant_type='digital',
            requires_shipping=False,
            price=Money(0, 'USD'),
        )

    def _prices(self):
        node = product_jsonld({'slug': 'offer-probe'}, model=self.product)
        return {v['sku']: v['offers']['price'] for v in node['hasVariant']}

    def test_a_free_download_is_offered_at_0(self):
        self.assertEqual(self._prices()['OP-1-D'], '0.00')

    def test_a_variant_that_ships_priced_0_is_offered_at_the_product_price(self):
        self.assertEqual(self._prices()['OP-1-P'], '16.00')
