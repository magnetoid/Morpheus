"""The dot_books product page: no raw originals, and its layout rules first.

* The "you might also like" grid rendered ``<img src="{{ p.primaryImage.url }}">``
  — the stored original, which for this catalogue is a multi-megabyte PNG —
  for a 260 px card, while every other cover goes through the responsive proxy
  (``/img/<fmt>/<w>/…``). Lighthouse measured 7.5 MB of oversized images on
  the live product page; three raw PNGs were 7.2 MB of it. The variant
  chooser's thumbnails and the ``<link rel="preload">`` of the hero did the
  same with the raw original (the hero itself renders the proxied AVIF, so the
  1.7 MB preload was a high-priority download nothing displayed).
* The two-column rule for ``.pdp-grid`` sat in a ``<style>`` AFTER the grid.
  The grid's inline style is single-column, so on a slow connection the
  details column was first laid out below the hero, off screen, and jumped up
  beside it when the stylesheet arrived — a layout shift of 0.275 on every
  Lighthouse run (threshold 0.1), identical across runs because the parse
  boundary is deterministic. Page CSS belongs in ``extra_head``.
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
        # Two variants on the first product so the PDP renders its variant chooser;
        # a variant without an image of its own thumbnails the product's primary image.
        from plugins.installed.catalog.models import ProductVariant

        first = Product.objects.get(slug='related-probe-1')
        for kind in ('physical', 'digital'):
            ProductVariant.objects.create(product=first, name=kind.title(), sku=f'RP-1-{kind[:3]}')

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

    def test_two_column_rule_precedes_the_grid(self):
        body = self.client.get('/products/related-probe-1/').content.decode()
        rule_at = body.index('grid-template-columns: 2fr 3fr')
        grid_at = body.index('class="pdp-grid"')
        head_ends = body.index('</head>')
        self.assertLess(rule_at, head_ends, 'the two-column rule is not in <head>')
        self.assertLess(rule_at, grid_at)

    def test_hero_is_not_preloaded_as_the_raw_original(self):
        body = self.client.get('/products/related-probe-1/').content.decode()
        self.assertNotIn('<link rel="preload" as="image" href="/media/', body)

    def test_variant_thumbnails_go_through_the_responsive_proxy(self):
        import re

        body = self.client.get('/products/related-probe-1/').content.decode()
        thumbs = re.findall(r'<span class="pdp-variant__thumb">(.*?)</span>', body, re.S)
        self.assertEqual(len(thumbs), 2, 'variant chooser not rendered — fixture drift')
        for thumb in thumbs:
            self.assertIn('/img/webp/', thumb, thumb)
            self.assertNotIn('src="/media/', thumb, thumb)
        # Nothing else on the page may print the raw original as an image source.
        # Known exception: the web-stories AMP player's poster. The player looks for
        # a bare <img data-amp-story-player-poster-img>, so it cannot take a
        # <picture>; live it uses the product's WebP variant (~80 KB).
        raw = [
            body[max(0, m.start() - 160) : m.end()]
            for m in re.finditer(r'src="/media/products/related-probe-1\.png"', body)
        ]
        raw = [r for r in raw if 'amp-story-player' not in r]
        self.assertEqual(raw, [], raw)
