"""Google Shopping feed — mapping, XML render, eligibility, endpoint."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from xml.etree import ElementTree as ET

from django.core.files.base import ContentFile
from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductImage
from plugins.installed.google_shopping.services.feed import build_feed
from plugins.installed.google_shopping.services.mapping import map_product
from plugins.installed.google_shopping.services.settings import feed_settings

_G = '{http://base.google.com/ns/1.0}'

# 1×1 transparent GIF — a real image file so primary_image resolves.
_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
    b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


def _product(slug, sku, *, price='9.00', compare=None, status='active', image=True):
    p = Product.objects.create(
        name=slug.replace('-', ' ').title(),
        slug=slug,
        sku=sku,
        price=Money(Decimal(price), 'USD'),
        compare_at_price=Money(Decimal(compare), 'USD') if compare else None,
        product_type='simple',
        status=status,
    )
    if image:
        pi = ProductImage(product=p, is_primary=True, sort_order=0)
        pi.image.save(f'{slug}.gif', ContentFile(_GIF), save=True)
    return p


class MappingTests(TestCase):
    def test_basic_item_has_required_attrs(self):
        p = _product('dune', 'SKU1')
        item = map_product(p, feed_settings())
        self.assertIsNotNone(item)
        for k in ('id', 'title', 'link', 'image_link', 'price', 'availability', 'condition'):
            self.assertIn(k, item)
        self.assertEqual(item['id'], 'SKU1')
        self.assertEqual(item['price'], '9.00 USD')
        self.assertEqual(item['condition'], 'new')
        # No identifier → identifier_exists must be 'no'.
        self.assertEqual(item.get('identifier_exists'), 'no')

    def test_sale_price_only_when_on_sale(self):
        plain = map_product(_product('a', 'A'), feed_settings())
        self.assertNotIn('sale_price', plain)
        on_sale = map_product(_product('b', 'B', price='6.00', compare='10.00'), feed_settings())
        self.assertEqual(on_sale['price'], '10.00 USD')  # regular = compare_at
        self.assertEqual(on_sale['sale_price'], '6.00 USD')  # sale = current

    def test_product_without_image_is_skipped(self):
        self.assertIsNone(map_product(_product('c', 'C', image=False), feed_settings()))

    def test_excluded_via_metafield_is_skipped(self):
        from plugins.installed.metafields.models import Metafield

        p = _product('d', 'D')
        Metafield.objects.set(p, namespace='google', key='excluded', value=True)
        self.assertIsNone(map_product(p, feed_settings()))

    def test_metafield_brand_and_condition_override(self):
        from plugins.installed.metafields.models import Metafield

        p = _product('e', 'E')
        Metafield.objects.set(p, namespace='google', key='brand', value='Penguin')
        Metafield.objects.set(p, namespace='google', key='condition', value='used')
        item = map_product(p, feed_settings())
        self.assertEqual(item['brand'], 'Penguin')
        self.assertEqual(item['condition'], 'used')


class VariantExpansionTests(TestCase):
    def test_variable_product_emits_one_item_per_variant(self):
        from plugins.installed.catalog.models import ProductVariant
        from plugins.installed.google_shopping.services.mapping import expand_variants

        p = Product.objects.create(
            name='Anthology',
            slug='anthology',
            sku='ANTH',
            price=Money(Decimal('9.00'), 'USD'),
            product_type='variable',
            status='active',
        )
        pi = ProductImage(product=p, is_primary=True, sort_order=0)
        pi.image.save('anth.gif', ContentFile(_GIF), save=True)
        ProductVariant.objects.create(
            product=p,
            name='Paperback',
            sku='ANTH-PB',
            price=Money(Decimal('9.00'), 'USD'),
            barcode='9780000000001',
        )
        ProductVariant.objects.create(
            product=p,
            name='Hardcover',
            sku='ANTH-HC',
            price=Money(Decimal('15.00'), 'USD'),
        )

        base = map_product(p, feed_settings())
        items = expand_variants(p, base, feed_settings())
        self.assertEqual(len(items), 2)
        ids = {i['id'] for i in items}
        self.assertEqual(ids, {'ANTH-PB', 'ANTH-HC'})
        for i in items:
            self.assertEqual(i['item_group_id'], 'ANTH')  # shared group = product
        pb = next(i for i in items if i['id'] == 'ANTH-PB')
        self.assertEqual(pb['gtin'], '9780000000001')  # variant barcode → gtin
        self.assertNotIn('identifier_exists', pb)  # has a gtin now
        hc = next(i for i in items if i['id'] == 'ANTH-HC')
        self.assertEqual(hc['price'], '15.00 USD')  # per-variant price
        self.assertIn('Hardcover', hc['title'])

    def test_simple_product_not_expanded(self):
        from plugins.installed.google_shopping.services.mapping import expand_variants

        p = _product('solo', 'SOLO')
        self.assertIsNone(expand_variants(p, map_product(p, feed_settings()), feed_settings()))


class FeedRenderTests(TestCase):
    def test_feed_is_wellformed_and_namespaced(self):
        _product('one', 'O1')
        _product('two', 'O2')
        xml, stats = build_feed(log=False)
        root = ET.fromstring(xml)  # raises if malformed
        items = root.findall('.//item')
        self.assertEqual(len(items), 2)
        self.assertEqual(stats['items'], 2)
        # g: namespace present on price.
        self.assertTrue(items[0].find(f'{_G}price') is not None)

    def test_inactive_product_absent(self):
        _product('live', 'L1')
        _product('draft', 'D1', status='draft')
        xml, stats = build_feed(log=False)
        self.assertEqual(stats['items'], 1)
        self.assertNotIn('draft', xml)


class EndpointTests(TestCase):
    def test_feed_endpoint_serves_xml(self):
        _product('z', 'Z1')
        r = Client().get('/feeds/google-merchant.xml')
        self.assertEqual(r.status_code, 200)
        self.assertIn('application/xml', r['Content-Type'])
        self.assertIn('http://base.google.com/ns/1.0', r.content.decode())
