"""The Merchant Center push sends shoppable products only, like the feed file.

A service product (a booking listing's) has no product page and cannot be added to a
cart; pushed to Merchant Center, its link redirects and the item is disapproved.
"""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product


class ContentApiShoppableTests(TestCase):
    def test_the_push_never_maps_a_service_product(self):
        from plugins.installed.google_shopping.services import content_api

        Product.objects.create(
            name='Mug', slug='mug', sku='MUG', status='active', price=Money(Decimal('9'), 'EUR')
        )
        Product.objects.create(
            name='Tour',
            slug='tour',
            sku='TOUR',
            status='active',
            product_type='service',
            price=Money(Decimal('50'), 'EUR'),
        )
        seen = []
        with (
            mock.patch.object(content_api, 'is_connected', return_value=True),
            mock.patch.object(content_api, 'raw_config', return_value={'merchant_id': '123'}),
            mock.patch.object(
                content_api, 'map_product', side_effect=lambda p, s: seen.append(p.slug)
            ),
        ):
            content_api.push_products(dry_run=True)
        self.assertEqual(seen, ['mug'])
