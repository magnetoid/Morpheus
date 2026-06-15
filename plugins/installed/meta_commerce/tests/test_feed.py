"""Meta catalog feed — mapping (Meta value formats), XML, variants, endpoint."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from xml.etree import ElementTree as ET

from django.core.files.base import ContentFile
from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductImage, ProductVariant
from plugins.installed.meta_commerce.services.feed import build_feed
from plugins.installed.meta_commerce.services.mapping import expand_variants, map_product
from plugins.installed.meta_commerce.services.settings import meta_settings

_G = '{http://base.google.com/ns/1.0}'
_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
    b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


def _product(slug, sku, *, price='9.00', compare=None, status='active', image=True, ptype='simple'):
    p = Product.objects.create(
        name=slug.replace('-', ' ').title(),
        slug=slug,
        sku=sku,
        price=Money(Decimal(price), 'USD'),
        compare_at_price=Money(Decimal(compare), 'USD') if compare else None,
        product_type=ptype,
        status=status,
    )
    if image:
        ProductImage(product=p, is_primary=True, sort_order=0).image.save(
            f'{slug}.gif', ContentFile(_GIF), save=True
        )
    return p


class MappingTests(TestCase):
    def test_meta_value_formats(self):
        item = map_product(_product('dune', 'SKU1'), meta_settings())
        self.assertEqual(item['availability'], 'in stock')  # Meta format (spaces)
        self.assertEqual(item['price'], '9.00 USD')
        self.assertEqual(item['condition'], 'new')

    def test_sale_price(self):
        item = map_product(_product('b', 'B', price='6.00', compare='10.00'), meta_settings())
        self.assertEqual(item['price'], '10.00 USD')
        self.assertEqual(item['sale_price'], '6.00 USD')

    def test_excluded_via_meta_metafield(self):
        from plugins.installed.metafields.models import Metafield

        p = _product('x', 'X')
        Metafield.objects.set(p, namespace='meta', key='excluded', value=True)
        self.assertIsNone(map_product(p, meta_settings()))

    def test_no_image_skipped(self):
        self.assertIsNone(map_product(_product('n', 'N', image=False), meta_settings()))


class VariantTests(TestCase):
    def test_variant_items_share_item_group_id(self):
        p = _product('anth', 'ANTH', ptype='variable')
        ProductVariant.objects.create(
            product=p, name='PB', sku='ANTH-PB', price=Money(Decimal('9'), 'USD')
        )
        ProductVariant.objects.create(
            product=p, name='HC', sku='ANTH-HC', price=Money(Decimal('15'), 'USD')
        )
        items = expand_variants(p, map_product(p, meta_settings()), meta_settings())
        self.assertEqual(len(items), 2)
        self.assertTrue(all(i['item_group_id'] == 'ANTH' for i in items))


class FeedTests(TestCase):
    def test_feed_wellformed_namespaced(self):
        _product('one', 'O1')
        _product('two', 'O2')
        xml, stats = build_feed(log=False)
        root = ET.fromstring(xml)
        self.assertEqual(len(root.findall('.//item')), 2)
        self.assertIsNotNone(root.find(f'.//item/{_G}price'))

    def test_endpoint_serves_xml(self):
        _product('z', 'Z1')
        r = Client().get('/feeds/meta-catalog.xml')
        self.assertEqual(r.status_code, 200)
        self.assertIn('application/xml', r['Content-Type'])
