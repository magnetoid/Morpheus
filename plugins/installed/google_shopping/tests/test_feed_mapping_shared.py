"""Golden regression for the shared channel feed resolver.

All six catalog channels resolve through ``plugins.feed_mapping.FeedMapper``.
These goldens were captured from the six pre-consolidation per-channel
resolvers (2026-07), so they pin the exact feed output merchants' live
channels already ingest: the five non-Google channels must produce
identical items; Google adds its underscored availability +
identifier_exists + content_language.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import importlib
from decimal import Decimal

from django.core.files.base import ContentFile
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductImage, ProductVariant

_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
    b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)

CHANNELS = {
    'google_shopping': 'feed_settings',
    'meta_commerce': 'meta_settings',
    'pinterest_commerce': 'pinterest_settings',
    'snapchat_commerce': 'snapchat_settings',
    'tiktok_commerce': 'tiktok_settings',
    'microsoft_commerce': 'microsoft_settings',
}

# The five spaced-availability channels share this exact item shape.
_COMMON_SIMPLE = {
    'id': 'SKU1',
    'title': 'Dune',
    'description': 'Dune',
    'link': 'https://localhost/products/dune/',
    'availability': 'in stock',
    'price': '10.00 USD',
    'condition': 'new',
    'sale_price': '6.00 USD',
}
_GOOGLE_SIMPLE = {
    **_COMMON_SIMPLE,
    'availability': 'in_stock',
    'identifier_exists': 'no',
    'content_language': 'en',
}


def _fixtures():
    p = Product.objects.create(
        name='Dune',
        slug='dune',
        sku='SKU1',
        price=Money(Decimal('6.00'), 'USD'),
        compare_at_price=Money(Decimal('10.00'), 'USD'),
        product_type='simple',
        status='active',
    )
    pi = ProductImage(product=p, is_primary=True, sort_order=0)
    pi.image.save('dune.gif', ContentFile(_GIF), save=True)

    v = Product.objects.create(
        name='Shirt',
        slug='shirt',
        sku='GRP',
        price=Money(Decimal('20.00'), 'USD'),
        product_type='variable',
        status='active',
    )
    vi = ProductImage(product=v, is_primary=True, sort_order=0)
    vi.image.save('shirt.gif', ContentFile(_GIF), save=True)
    ProductVariant.objects.create(
        product=v, name='Small', sku='GRP-S', price=Money(Decimal('20.00'), 'USD')
    )
    ProductVariant.objects.create(
        product=v, name='Large', sku='GRP-L', price=Money(Decimal('22.00'), 'USD')
    )
    return p, v


def _mapped(channel, factory, product):
    mapping = importlib.import_module(f'plugins.installed.{channel}.services.mapping')
    settings_mod = importlib.import_module(f'plugins.installed.{channel}.services.settings')
    return mapping, getattr(settings_mod, factory)(), product


def _strip_image(item):
    out = dict(item)
    out.pop('image_link', None)
    return out


class FeedMappingGoldenTests(TestCase):
    def test_simple_item_matches_pre_consolidation_golden(self):
        p, _v = _fixtures()
        for channel, factory in CHANNELS.items():
            mapping, fs, _ = _mapped(channel, factory, p)
            item = mapping.map_product(p, fs)
            self.assertIsNotNone(item, channel)
            expected = _GOOGLE_SIMPLE if channel == 'google_shopping' else _COMMON_SIMPLE
            self.assertEqual(_strip_image(item), expected, channel)
            self.assertTrue(item['image_link'].startswith('https://localhost/media/'), channel)

    def test_variant_expansion_matches_golden(self):
        _p, v = _fixtures()
        for channel, factory in CHANNELS.items():
            mapping, fs, _ = _mapped(channel, factory, v)
            base = mapping.map_product(v, fs)
            items = mapping.expand_variants(v, base, fs)
            self.assertEqual(len(items), 2, channel)
            self.assertEqual([i['id'] for i in items], ['GRP-S', 'GRP-L'], channel)
            self.assertEqual([i['item_group_id'] for i in items], ['GRP', 'GRP'], channel)
            self.assertEqual([i['price'] for i in items], ['20.00 USD', '22.00 USD'], channel)
            self.assertEqual(
                [i['title'] for i in items], ['Shirt — Small', 'Shirt — Large'], channel
            )

    def test_five_channels_emit_identical_items(self):
        p, _v = _fixtures()
        seen = []
        for channel, factory in CHANNELS.items():
            if channel == 'google_shopping':
                continue
            mapping, fs, _ = _mapped(channel, factory, p)
            seen.append(_strip_image(mapping.map_product(p, fs)))
        self.assertTrue(all(s == seen[0] for s in seen))
