"""The dot_books product page must not ship raw originals for related books.

The "you might also like" grid rendered ``<img src="{{ p.primaryImage.url }}">``
— the stored original, which for this catalogue is a multi-megabyte PNG — for
a 260 px card, while every other cover on the storefront goes through the
responsive proxy (``/img/<fmt>/<w>/…``). Lighthouse measured 7.5 MB of
oversized images on the live product page; three raw PNGs were 7.2 MB of it.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from djmoney.money import Money

from themes.registry import theme_registry


class DotBooksPdpImagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Product, ProductImage

        category = Category.objects.create(name='PDP Images', slug='pdp-images')
        for i in (1, 2, 3):
            product = Product.objects.create(
                name=f'Related Probe {i}',
                slug=f'related-probe-{i}',
                sku=f'RP-{i}',
                price=Money(Decimal('9.00'), 'USD'),
                product_type='simple',
                status='active',
                category=category,
            )
            ProductImage.objects.create(
                product=product, image=f'products/related-probe-{i}.png', is_primary=True
            )

    def setUp(self):
        cache.clear()
        override = override_settings(MORPHEUS_ACTIVE_THEME='dot_books')
        override.enable()
        self.addCleanup(override.disable)
        previous = theme_registry._active_name
        theme_registry.set_active('dot_books')
        self.addCleanup(setattr, theme_registry, '_active_name', previous)

    def test_related_grid_covers_go_through_the_responsive_proxy(self):
        body = self.client.get('/products/related-probe-1/').content.decode()
        related = body[body.index('id="related"') :]
        self.assertIn('/img/webp/', related, 'no related cover rendered — fixture drift')
        self.assertNotIn('src="/media/products/related-probe-', related)
