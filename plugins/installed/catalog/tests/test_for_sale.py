"""What the basket takes: ``is_for_sale`` on a product and its editions.

The live Dawnchild store (read 2026-11-21) carries books nothing prices yet: The
Dawnchild has an unpriced paperback beside a free audiobook, and Daffy Goes to
Sea has no edition at all, both on a product priced 0. The basket refuses such a
copy ("not available to buy yet"), while the home shelf printed $0.00 with an
"Add to basket" button and the book page selected the paperback first. The rule
the storefront reads is the basket's own: a copy is for sale when it is given
away or priced above 0, its own price or the book's.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from api.client import internal_graphql
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.orders.models import Cart
from plugins.installed.orders.services import CartService
from plugins.testing import set_app_settings

_Q = """
query ForSale($slug: String!) {
  product(slug: $slug) {
    isForSale defaultVariantId
    variants { sku isForSale }
  }
}
"""


def _product(slug, price='0'):
    return Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal(price), 'USD'),
        product_type='simple',
        status='active',
    )


def _paperback(product, price=None, sort_order=0):
    return ProductVariant.objects.create(
        product=product,
        name='Paperback',
        sku=f'{product.slug}-pb',
        price=price,
        variant_type='physical',
        sort_order=sort_order,
    )


def _audiobook(product, sort_order=1):
    return ProductVariant.objects.create(
        product=product,
        name='Audiobook',
        sku=f'{product.slug}-ab',
        price=Money(0, 'USD'),
        variant_type='audiobook',
        requires_shipping=False,
        sort_order=sort_order,
    )


class ForSaleTests(TestCase):
    def setUp(self):
        cache.clear()

    def _add(self, product, variant=None):
        cart = Cart.objects.create(session_key=f'for-sale-{Cart.objects.count()}')
        return CartService.add_item(cart, str(product.id), 1, str(variant.id) if variant else None)

    def test_an_unpriced_paperback_beside_a_free_audiobook(self):
        book = _product('dawn')
        paperback, audio = _paperback(book), _audiobook(book)
        self.assertFalse(paperback.is_for_sale)
        self.assertTrue(audio.is_for_sale)
        self.assertTrue(book.is_for_sale)
        # The basket agrees with the rule, both ways.
        with self.assertRaisesMessage(ValueError, 'not available to buy yet'):
            self._add(book, paperback)
        self.assertEqual(self._add(book, audio).unit_price, Money(0, 'USD'))
        node = internal_graphql(_Q, {'slug': 'dawn'})['product']
        self.assertTrue(node['isForSale'])
        self.assertEqual(
            {v['sku']: v['isForSale'] for v in node['variants']},
            {'dawn-pb': False, 'dawn-ab': True},
        )
        # The page selects the copy that can be had, never the one the basket refuses.
        self.assertEqual(node['defaultVariantId'], str(audio.pk))

    def test_a_book_with_no_edition_and_no_price_is_not_for_sale(self):
        book = _product('daffy')
        self.assertFalse(book.is_for_sale)
        self.assertFalse(internal_graphql(_Q, {'slug': 'daffy'})['product']['isForSale'])
        with self.assertRaisesMessage(ValueError, 'not available to buy yet'):
            self._add(book)

    def test_a_priced_book_sells_its_unpriced_paperback_at_the_book_price(self):
        # dotbooks: a printed edition with no price of its own takes the book's.
        book = _product('priced', price='18.00')
        paperback, audio = _paperback(book), _audiobook(book)
        self.assertTrue(paperback.is_for_sale)
        self.assertTrue(book.is_for_sale)
        node = internal_graphql(_Q, {'slug': 'priced'})['product']
        # The edition that costs something is still selected first.
        self.assertEqual(node['defaultVariantId'], str(paperback.pk))
        self.assertTrue(audio.is_for_sale)

    def test_a_priced_book_with_no_edition_is_for_sale(self):
        self.assertTrue(_product('plain', price='5.00').is_for_sale)

    def test_giving_print_away_puts_the_paperback_on_sale(self):
        book = _product('given')
        paperback = _paperback(book)
        _audiobook(book)
        set_app_settings(self, 'catalog', give_away_print=True)
        self.assertTrue(paperback.is_for_sale)
        self.assertEqual(self._add(book, paperback).unit_price, Money(0, 'USD'))

    def test_an_inactive_edition_counts_for_nothing(self):
        book = _product('retired')
        audio = _audiobook(book)
        audio.is_active = False
        audio.save(update_fields=['is_active'])
        _paperback(book)
        self.assertFalse(Product.objects.get(pk=book.pk).is_for_sale)
