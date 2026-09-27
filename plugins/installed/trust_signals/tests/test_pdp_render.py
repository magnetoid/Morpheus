"""The trust strip renders on the real product page.

The storefront PDP passes its blocks the GraphQL product *dict*, not the model.
`collect_trust_data` read `getattr(product, 'pk', None)` — always None on a
dict — and returned `{}`, so the rating / verified-buyer / recent-purchases
strip never appeared on any live PDP, with nothing logged to say why.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, Review
from plugins.installed.customers.models import Customer


class TrustStripPdpTests(TestCase):
    def setUp(self):
        cache.clear()
        self.product = Product.objects.create(
            name='Well Reviewed',
            slug='well-reviewed-probe',
            sku='TS-1',
            status='active',
            price=Money(Decimal('12.00'), 'USD'),
        )
        for i in range(3):
            customer = Customer.objects.create_user(
                email=f'reader{i}@example.com', username=f'reader{i}', password='pw-12345678'
            )
            Review.objects.create(
                product=self.product, customer=customer, rating=5, body='Lovely.', is_approved=True
            )

    def test_rating_renders_on_the_pdp(self):
        response = self.client.get('/products/well-reviewed-probe/')
        self.assertEqual(response.status_code, 200)
        # `trust-strip__rating` is this block's own class; the theme's static
        # strip uses `trust-strip__item`, so this cannot match theme markup.
        self.assertIn('trust-strip__rating', response.content.decode())
