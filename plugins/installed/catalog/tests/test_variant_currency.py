"""A variant priced without an explicit currency is priced in its product's.

`catalog.create_variant` / `catalog.update_variant` (MCP + GraphQL) take
`price_currency` as optional. `_apply_variant_fields` fell back to the variant's
own price currency — which a new variant (or one inheriting its product's price)
does not have — and then to a hardcoded 'USD'. On a store that sells in EUR an
agent adding "30 ml — 14.50" created a USD variant inside a EUR product: the
picker showed dollars and the line could not share a cart with anything else.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.catalog.services import create_variant, update_variant


class VariantCurrencyTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Lavender Oil',
            slug='lavender-oil',
            sku='LAV-1',
            status='active',
            product_type='variable',
            price=Money(Decimal('0.00'), 'EUR'),
        )

    def test_new_variant_is_priced_in_its_products_currency(self):
        out = create_variant(
            product_slug='lavender-oil',
            name='30 ml',
            sku='LAV-30',
            price_amount='14.50',
            compare_at_amount='18.00',
        )
        v = ProductVariant.objects.get(sku='LAV-30')
        self.assertEqual(str(v.price.currency), 'EUR')
        self.assertEqual(str(v.compare_at_price.currency), 'EUR')
        self.assertEqual(out['price_currency'], 'EUR')

    def test_pricing_an_inheriting_variant_keeps_the_products_currency(self):
        ProductVariant.objects.create(product=self.product, name='10 ml', sku='LAV-10')
        update_variant(sku='LAV-10', price_amount='6.90')
        self.assertEqual(str(ProductVariant.objects.get(sku='LAV-10').price.currency), 'EUR')

    def test_an_explicit_currency_is_still_honoured(self):
        create_variant(
            product_slug='lavender-oil',
            name='50 ml',
            sku='LAV-50',
            price_amount='19.00',
            price_currency='usd',
        )
        self.assertEqual(str(ProductVariant.objects.get(sku='LAV-50').price.currency), 'USD')
