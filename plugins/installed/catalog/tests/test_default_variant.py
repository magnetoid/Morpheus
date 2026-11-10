"""A product sold in one form counts its stock on a default variant (v0.152.0):
named "Default", no size, no price of its own, made the first time stock is
entered. The product page offers no choice for it (``hasOnlyDefaultVariant``)."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.catalog.variants import (
    ensure_stock_variant,
    has_only_default_variant,
    stock_variant,
)


class EnsureStockVariantTests(TestCase):
    def test_a_one_form_product_gets_one_default_variant(self):
        product = Product.objects.create(
            name='Mug', slug='mug', sku='MUG', price=8, weight=Decimal('0.4')
        )
        variant = ensure_stock_variant(product)
        self.assertEqual((variant.name, variant.sku, variant.size), ('Default', 'MUG', ''))
        self.assertIsNone(variant.price)
        self.assertEqual(variant.weight, Decimal('0.4'))
        self.assertEqual(ensure_stock_variant(product), variant)
        self.assertEqual(product.variants.count(), 1)

    def test_a_taken_sku_gets_a_suffix(self):
        other = Product.objects.create(name='Other', slug='other', sku='OTHER', price=1)
        ProductVariant.objects.create(product=other, name='Std', sku='MUG')
        product = Product.objects.create(name='Mug', slug='mug', sku='MUG', price=8)
        self.assertEqual(ensure_stock_variant(product).sku, 'MUG-default')

    def test_variable_unstocked_and_many_variant_products_get_none(self):
        for kind in ('variable', 'digital', 'service'):
            product = Product.objects.create(
                name=kind, slug=f'p-{kind}', sku=f'P-{kind}', price=1, product_type=kind
            )
            self.assertIsNone(ensure_stock_variant(product), kind)
        product = Product.objects.create(name='Two', slug='two', sku='TWO', price=1)
        ProductVariant.objects.create(product=product, name='A', sku='TWO-A')
        ProductVariant.objects.create(product=product, name='B', sku='TWO-B')
        self.assertIsNone(stock_variant(product))
        self.assertIsNone(ensure_stock_variant(product))
        self.assertEqual(product.variants.count(), 2)


class OnlyDefaultVariantTests(TestCase):
    def test_only_a_lone_default_row_offers_no_choice(self):
        product = Product.objects.create(name='Mug', slug='mug', sku='MUG', price=8)
        self.assertFalse(has_only_default_variant(product))
        variant = ensure_stock_variant(product)
        self.assertTrue(has_only_default_variant(product))
        variant.size = 'Large'
        variant.save()
        self.assertFalse(has_only_default_variant(product))
        variant.size = ''
        variant.name = 'Default Title'  # Shopify's name for the same row
        variant.save()
        self.assertTrue(has_only_default_variant(product))
        ProductVariant.objects.create(
            product=product, name='Gift box', sku='MUG-G', price=Money(Decimal('12'), 'USD')
        )
        self.assertFalse(has_only_default_variant(product))
