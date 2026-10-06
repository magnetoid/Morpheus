"""A dynamics carousel must not ship the raw original of every cover.

``_carousel.html`` rendered ``<img src="{{ product.primary_image.image.url }}">``
— the stored original, a multi-megabyte PNG for this catalogue — for a 260 px
card, while the theme's own cards go through the responsive proxy. On the live
product page three raw PNGs from this carousel and the related grid were
7.2 MB of a 7.5 MB "oversized images" finding.
"""

from __future__ import annotations

from decimal import Decimal

from django.template.loader import render_to_string
from django.test import TestCase
from djmoney.money import Money


class CarouselImagesTests(TestCase):
    def test_covers_go_through_the_responsive_proxy(self):
        from plugins.installed.catalog.models import Product, ProductImage

        product = Product.objects.create(
            name='Carousel Probe',
            slug='carousel-probe',
            sku='CAR-1',
            price=Money(Decimal('9.00'), 'USD'),
            status='active',
        )
        ProductImage.objects.create(
            product=product, image='products/carousel-probe.png', is_primary=True
        )

        html = render_to_string(
            'dynamics/_carousel.html', {'products': [product], 'heading': 'Picks'}
        )

        self.assertIn('/img/webp/', html)
        self.assertNotIn('src="/media/products/carousel-probe.png"', html)
