"""What a variant is on each axis Google reads (v0.163.0).

`catalog.variants.variant_axes` reads the variant's size field and its
variant attributes (`Attribute.is_variant`) named size, color/colour, material
or pattern, the axes on Google's product variants page
(https://developers.google.com/search/docs/appearance/structured-data/product-variants)
that a catalog can state.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Attribute, AttributeValue, Product, ProductVariant
from plugins.installed.catalog.variants import variant_axes


def _value(attribute, name):
    return AttributeValue.objects.create(attribute=attribute, name=name, slug=name.lower())


class VariantAxesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Shirt',
            slug='shirt-axes',
            sku='SH-1',
            status='active',
            price=Money(Decimal('20.00'), 'USD'),
        )
        cls.colour = Attribute.objects.create(name='Colour', slug='colour', is_variant=True)
        cls.material = Attribute.objects.create(name='Material', slug='material', is_variant=False)
        cls.fit = Attribute.objects.create(name='Fit', slug='fit', is_variant=True)

    def _variant(self, sku, size='', values=()):
        variant = ProductVariant.objects.create(
            product=self.product, name=sku, sku=sku, size=size, price=Money(Decimal('20.00'), 'USD')
        )
        variant.attribute_values.set(values)
        return variant

    def test_size_and_a_variant_colour(self):
        variant = self._variant('SH-R-M', size=' M ', values=[_value(self.colour, 'Red')])
        self.assertEqual(variant_axes(variant), {'size': 'M', 'color': 'Red'})

    def test_a_descriptive_attribute_is_not_an_axis(self):
        # "Material" here is a filter on the product, not one of its choices.
        variant = self._variant('SH-COT', values=[_value(self.material, 'Cotton')])
        self.assertEqual(variant_axes(variant), {})

    def test_an_axis_google_does_not_read_is_left_out(self):
        variant = self._variant('SH-SLIM', values=[_value(self.fit, 'Slim')])
        self.assertEqual(variant_axes(variant), {})

    def test_an_unsaved_variant_says_only_its_size(self):
        self.assertEqual(variant_axes(ProductVariant(size='XL')), {'size': 'XL'})
