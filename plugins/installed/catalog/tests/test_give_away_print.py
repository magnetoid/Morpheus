"""A store can give printed copies away (owner, 2026-11-21: "Give print away").

On a variant that ships, 0 means "use the book's price" (dotbooks sells ten printed
editions that carry a 0), and an edition nothing prices is not sold. The Dawnchild
store gives its books away, print included, so catalog's ``give_away_print``
setting (off by default) makes such a copy free: a printed edition with no price
above 0 of a book priced 0. A printed edition of a book that has a price stays
the book's price whatever the setting says.
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
query Free($slug: String!) {
  product(slug: $slug) {
    isFree priceStartsFrom price { amount }
    variants { sku isFree price { amount currency } }
  }
}
"""


def _book(slug, *, price='0', paperback_price=None):
    """A book with a printed paperback (no price, or ``paperback_price``) and a
    free audiobook, like The Dawnchild on the live store."""
    book = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal(price), 'USD'),
        product_type='variable',
        status='active',
    )
    paperback = ProductVariant.objects.create(
        product=book,
        name='Paperback',
        sku=f'{slug}-pb',
        price=paperback_price,
        variant_type='physical',
        sort_order=0,
    )
    audio = ProductVariant.objects.create(
        product=book,
        name='Audiobook',
        sku=f'{slug}-ab',
        price=Money(0, 'USD'),
        variant_type='audiobook',
        requires_shipping=False,
        sort_order=1,
    )
    return book, paperback, audio


class GiveAwayPrintTests(TestCase):
    def setUp(self):
        cache.clear()
        self.book, self.paperback, self.audio = _book('bird')
        self.zero_paperback = ProductVariant.objects.create(
            product=self.book,
            name='Hardback',
            sku='bird-hb',
            price=Money(0, 'USD'),
            variant_type='physical',
            sort_order=2,
        )

    def _add(self, variant=None, product=None):
        cart = Cart.objects.create(session_key=f'give-away-{Cart.objects.count()}')
        return CartService.add_item(
            cart, str((product or self.book).id), 1, str(variant.id) if variant else None
        )

    def test_off_by_default_an_unpriced_printed_copy_is_not_sold(self):
        self.assertFalse(self.paperback.is_free)
        self.assertFalse(self.zero_paperback.is_free)
        self.assertFalse(self.book.is_free)
        with self.assertRaisesMessage(ValueError, 'not available to buy yet'):
            self._add(self.paperback)

    def test_on_a_printed_copy_nothing_prices_is_free(self):
        set_app_settings(self, 'catalog', give_away_print=True)
        for variant in (self.paperback, self.zero_paperback):
            with self.subTest(variant=variant.sku):
                self.assertTrue(variant.is_free)
                self.assertEqual(variant.effective_price, Money(0, 'USD'))
        self.assertTrue(self.book.is_free)
        self.assertFalse(self.book.price_starts_from)

    def test_on_the_basket_takes_the_printed_copy_at_0_and_ships_it(self):
        set_app_settings(self, 'catalog', give_away_print=True)
        line = self._add(self.paperback)
        self.assertEqual(line.unit_price, Money(0, 'USD'))
        self.assertEqual(line.variant_id, self.paperback.id)

    def test_on_graphql_says_free_and_prices_the_copy_at_0(self):
        set_app_settings(self, 'catalog', give_away_print=True)
        node = internal_graphql(_Q, {'slug': 'bird'})['product']
        self.assertTrue(node['isFree'])
        variants = {v['sku']: v for v in node['variants']}
        self.assertTrue(variants['bird-pb']['isFree'])
        self.assertEqual(Decimal(variants['bird-pb']['price']['amount']), Decimal('0'))
        self.assertEqual(variants['bird-pb']['price']['currency'], 'USD')

    def test_a_printed_copy_of_a_priced_book_keeps_the_book_price(self):
        # dotbooks: a printed edition carrying 0 is sold at the book's price.
        set_app_settings(self, 'catalog', give_away_print=True)
        book, paperback, _audio = _book('priced', price='23.00', paperback_price=Money(0, 'USD'))
        self.assertFalse(paperback.is_free)
        self.assertEqual(paperback.effective_price, Money(Decimal('23.00'), 'USD'))
        self.assertFalse(book.is_free)
        self.assertEqual(
            self._add(paperback, product=book).unit_price, Money(Decimal('23.00'), 'USD')
        )

    def test_a_printed_copy_with_its_own_price_is_sold_at_it(self):
        set_app_settings(self, 'catalog', give_away_print=True)
        _book_, paperback, _audio = _book('own', paperback_price=Money(Decimal('9.00'), 'USD'))
        self.assertFalse(paperback.is_free)

    def test_a_free_book_added_without_a_format_names_its_copy(self):
        # Two copies given away: the basket asks which.
        set_app_settings(self, 'catalog', give_away_print=True)
        with self.assertRaisesMessage(ValueError, 'Choose a format first.'):
            self._add()
        # One copy: it is the line's.
        pdf_only = Product.objects.create(
            name='Pdf Only',
            slug='pdf-only',
            sku='PDF-ONLY',
            price=Money(0, 'USD'),
            product_type='variable',
            status='active',
        )
        pdf = ProductVariant.objects.create(
            product=pdf_only,
            name='Digital PDF',
            sku='pdf-only-pdf',
            price=Money(0, 'USD'),
            variant_type='digital',
            requires_shipping=False,
        )
        line = self._add(product=pdf_only)
        self.assertEqual(line.variant_id, pdf.id)
        self.assertEqual(line.unit_price, Money(0, 'USD'))

    def test_the_setting_is_read_again_by_every_worker(self):
        from plugins.registry import app_registry

        self.assertEqual(app_registry.get('catalog').config_fresh_s, 10.0)
