"""A manufacturer is who answers for a product, not its brand (v0.163.0).

catalog's brand source (`catalog/brand.py`) never reads the GPSR details, so a
product with a manufacturer and no brand still claims no brand.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.brand import product_brand
from plugins.installed.catalog.models import Product
from plugins.installed.product_safety.safety import set_details


class ManufacturerIsNotABrandTests(TestCase):
    def test_a_manufacturer_names_no_brand(self):
        product = Product.objects.create(
            name='Lamp',
            slug='lamp-gpsr',
            sku='LG-1',
            status='active',
            price=Money(Decimal('9.00'), 'EUR'),
            requires_shipping=True,
        )
        set_details(product, {'manufacturer_name': 'Lumen Works d.o.o.'})
        self.assertEqual(product_brand(product), '')

        from plugins.installed.seo.services.jsonld import product_jsonld

        self.assertNotIn('brand', product_jsonld(product, base_url='https://shop.test/'))
