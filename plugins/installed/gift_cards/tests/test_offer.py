"""The gift card a shopper can buy, for a theme's banner (v0.191.0).

Montenegro's home promised "Digital gift cards … From €25 to €500" and linked
/products/, where no gift card was for sale. A theme now shows the banner only
while the app names a gift-card product, and links to it.
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.gift_cards.context_processors import gift_card_offer


def _offer():
    cache.clear()
    return gift_card_offer(RequestFactory().get('/'))['gift_card_offer']


class GiftCardOfferTests(TestCase):
    def test_none_without_a_gift_card_product(self):
        Product.objects.create(
            name='Kayak', slug='kayak', sku='KAYAK', price=Money(10, 'EUR'), status='active'
        )
        self.assertIsNone(_offer())

    def test_the_product_and_its_price_range(self):
        product = Product.objects.create(
            name='Gift card',
            slug='gift-card',
            sku='GIFT-CARD',
            price=Money(25, 'EUR'),
            status='active',
        )
        for sku, amount in (('GIFT-CARD-25', 25), ('GIFT-CARD-500', 500)):
            ProductVariant.objects.create(
                product=product, sku=sku, name=sku, price=Money(amount, 'EUR')
            )
        offer = _offer()
        self.assertEqual(offer['url'], '/products/gift-card/')
        self.assertEqual(offer['low'], Money(25, 'EUR'))
        self.assertEqual(offer['high'], Money(500, 'EUR'))

    def test_one_price_is_no_range(self):
        Product.objects.create(
            name='Gift card',
            slug='gift-card',
            sku='GIFT-CARD',
            price=Money(50, 'EUR'),
            status='active',
        )
        offer = _offer()
        self.assertEqual(offer['low'], Money(50, 'EUR'))
        self.assertIsNone(offer['high'])

    def test_a_draft_is_not_for_sale(self):
        Product.objects.create(
            name='Gift card',
            slug='gift-card',
            sku='GIFT-CARD',
            price=Money(50, 'EUR'),
            status='draft',
        )
        self.assertIsNone(_offer())
