"""`Product.agentMetadata` is what AI shopping agents quote — it must match the shop.

The first-party SDK's `search_products` reads exactly `priceAmount`, `currency`,
`inStock` and `urlPath` from it. The resolver built all three from the wrong
source: the price from the parent row, which the product form zeroes for a
variable product (so every variable product was offered at 0.00 USD); stock from
`variant.is_active` (so a sold-out product was "in stock"); and the URL from
`/p/<slug>`, which is the CMS page route — every product link 404'd.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from api.client import internal_graphql
from plugins.installed.catalog.models import Product, ProductVariant

_Q = """
query ($slug: String!) { product(slug: $slug) {
  price { amount currency }
  agentMetadata { priceAmount currency inStock urlPath }
} }
"""


def _meta(slug):
    return internal_graphql(_Q, {'slug': slug})['product']


class AgentMetadataClaimsTests(TestCase):
    def test_variable_product_is_quoted_at_its_display_price_and_real_page(self):
        p = Product.objects.create(
            name='Atlas of Islands',
            slug='atlas-of-islands',
            sku='ATL-1',
            status='active',
            product_type='variable',
            price=Money(Decimal('0.00'), 'EUR'),
        )
        ProductVariant.objects.create(
            product=p, name='Paperback', sku='ATL-PB', price=Money(Decimal('18.00'), 'EUR')
        )
        ProductVariant.objects.create(
            product=p, name='Hardcover', sku='ATL-HC', price=Money(Decimal('32.00'), 'EUR')
        )

        data = _meta('atlas-of-islands')
        meta = data['agentMetadata']
        self.assertEqual(Decimal(meta['priceAmount']), Decimal(data['price']['amount']))
        self.assertEqual(Decimal(meta['priceAmount']), Decimal('18.00'))
        self.assertEqual(meta['currency'], 'EUR')
        self.assertEqual(meta['urlPath'], '/products/atlas-of-islands/')

    def test_sold_out_product_is_not_reported_in_stock(self):
        from plugins.installed.inventory.models import StockLevel, Warehouse

        p = Product.objects.create(
            name='Sold Out Guide',
            slug='sold-out-guide',
            sku='SOG-1',
            status='active',
            price=Money(Decimal('12.00'), 'EUR'),
        )
        v = ProductVariant.objects.create(product=p, name='Std', sku='SOG-V1')
        wh = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        StockLevel.objects.create(variant=v, warehouse=wh, quantity=0)

        self.assertFalse(_meta('sold-out-guide')['agentMetadata']['inStock'])
