"""A download priced 0 is free; a variant that ships is never free (owner, 2026-11-07).

dotbooks gives its PDF editions away. Before this, a price of 0 was the same as
no price everywhere (djmoney's Money(0) is falsy): the PDF fell back to the
book's price on the product page and at checkout, and the add-to-cart guard
refused anything at 0. Ten printed editions on dotbooks carry a 0 and are sold
at the book's price, so the rule is narrow: 0 means free only on a variant that
ships nothing (`ProductVariant.is_free`). A book with a free PDF is still shown
at its printed price (the card and the price above the editions), and its PDF
says Free where the editions are listed.
"""

from __future__ import annotations

import importlib
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from api.client import internal_graphql
from plugins.installed.catalog.models import Product, ProductVariant

_Q = """
query Free($slug: String!) {
  product(slug: $slug) {
    price { amount } priceStartsFrom defaultVariantId
    variants { id sku isFree price { amount } compareAtPrice { amount } isOnSale }
  }
}
"""


def _book(slug, *, compare_at=None):
    book = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('8.50'), 'USD'),
        compare_at_price=compare_at,
        product_type='variable',
        status='active',
    )
    pdf = ProductVariant.objects.create(
        product=book,
        name='Digital PDF',
        sku=f'{slug}-pdf',
        price=Money(0, 'USD'),
        variant_type='digital',
        requires_shipping=False,
        sort_order=0,
    )
    printed = ProductVariant.objects.create(
        product=book,
        name='Print',
        sku=f'{slug}-print',
        variant_type='physical',
        sort_order=1,
    )
    return book, pdf, printed


class FreeVariantRuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.book, cls.pdf, cls.printed = _book('free-rule')
        cls.zero_print = ProductVariant.objects.create(
            product=cls.book,
            name='Hardcover',
            sku='free-rule-hard',
            price=Money(0, 'USD'),
            variant_type='physical',
        )

    def test_a_download_priced_0_is_free(self):
        self.assertTrue(self.pdf.is_free)
        self.assertEqual(self.pdf.effective_price, Money(0, 'USD'))

    def test_a_variant_that_ships_is_never_free(self):
        self.assertFalse(self.zero_print.is_free)
        self.assertEqual(self.zero_print.effective_price, Money(Decimal('8.50'), 'USD'))

    def test_a_variant_without_a_price_takes_the_product_price(self):
        self.assertFalse(self.printed.is_free)
        self.assertEqual(self.printed.effective_price, Money(Decimal('8.50'), 'USD'))

    def test_a_download_without_a_price_is_not_free(self):
        pdf = ProductVariant(product=self.book, price=None, requires_shipping=False)
        self.assertFalse(pdf.is_free)


class FreeDownloadDisplayTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.book, cls.pdf, cls.printed = _book(
            'free-display', compare_at=Money(Decimal('12.00'), 'USD')
        )
        cls.all_free = Product.objects.create(
            name='All Free',
            slug='all-free',
            sku='ALL-FREE',
            price=Money(Decimal('5.00'), 'USD'),
            product_type='variable',
            status='active',
        )
        for kind in ('pdf', 'epub'):
            ProductVariant.objects.create(
                product=cls.all_free,
                name=kind,
                sku=f'all-free-{kind}',
                price=Money(0, 'USD'),
                variant_type='digital',
                requires_shipping=False,
            )

    def setUp(self):
        cache.clear()

    def _gql(self, slug):
        return internal_graphql(_Q, {'slug': slug})['product']

    def test_the_book_is_shown_at_its_printed_price(self):
        self.assertEqual(self.book.display_price, Money(Decimal('8.50'), 'USD'))
        # One paid edition: the price is what it costs, not a "From" price.
        self.assertFalse(self.book.price_starts_from)
        node = self._gql('free-display')
        self.assertEqual(Decimal(node['price']['amount']), Decimal('8.50'))
        self.assertFalse(node['priceStartsFrom'])

    def test_the_pdf_is_listed_at_0_and_says_it_is_free(self):
        variants = {v['sku']: v for v in self._gql('free-display')['variants']}
        pdf = variants['free-display-pdf']
        self.assertTrue(pdf['isFree'])
        self.assertEqual(Decimal(pdf['price']['amount']), Decimal('0'))
        # The book's was-price is not the free download's: no sale, no strikethrough.
        self.assertIsNone(pdf['compareAtPrice'])
        self.assertFalse(pdf['isOnSale'])
        printed = variants['free-display-print']
        self.assertFalse(printed['isFree'])
        self.assertEqual(Decimal(printed['price']['amount']), Decimal('8.50'))

    def test_the_page_selects_the_edition_that_costs_something_first(self):
        # The PDF sorts first; the page still opens on the printed book, so the
        # price above the editions is the one selected.
        self.assertEqual(self._gql('free-display')['defaultVariantId'], str(self.printed.pk))

    def test_a_book_whose_editions_are_all_free_shows_0(self):
        self.assertEqual(self.all_free.display_price, Money(0, 'USD'))
        node = self._gql('all-free')
        self.assertEqual(Decimal(node['price']['amount']), Decimal('0'))
        self.assertIsNotNone(node['defaultVariantId'])


class FreeDownloadFeedTests(TestCase):
    """Shopping channels refuse a price of 0, and the book's price would be a
    false claim for a free PDF: the feeds list only the paid editions, under the
    ids they already had."""

    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import ProductImage

        cls.book, cls.pdf, cls.printed = _book('free-feed')
        # A book with one free edition, and one whose editions are all free.
        cls.single, single_pdf, single_print = _book('free-single')
        single_print.delete()
        cls.all_free, _pdf, all_print = _book('free-all')
        all_print.is_active = False
        all_print.save()
        for product in (cls.book, cls.single, cls.all_free):
            # A stored name is all the feed reads; no file is written.
            ProductImage.objects.create(
                product=product, image=f'products/{product.slug}.png', is_primary=True
            )

    def _feeds(self):
        for channel, factory in (
            ('google_shopping', 'feed_settings'),
            ('meta_commerce', 'meta_settings'),
        ):
            mapping = importlib.import_module(f'plugins.installed.{channel}.services.mapping')
            settings_mod = importlib.import_module(f'plugins.installed.{channel}.services.settings')
            yield channel, mapping, getattr(settings_mod, factory)()

    def test_a_product_with_no_paid_edition_is_not_listed(self):
        # The feed builders list the product's own item when it has no
        # variant items, so a free-only product must not map at all.
        self.assertTrue(self.single.is_free)
        self.assertTrue(self.all_free.is_free)
        self.assertFalse(self.book.is_free)
        for channel, mapping, fs in self._feeds():
            self.assertIsNotNone(mapping.map_product(self.book, fs), channel)
            self.assertIsNone(mapping.map_product(self.single, fs), channel)
            self.assertIsNone(mapping.map_product(self.all_free, fs), channel)

    def test_every_channel_leaves_the_free_download_out(self):
        for channel, factory in (
            ('google_shopping', 'feed_settings'),
            ('meta_commerce', 'meta_settings'),
        ):
            mapping = importlib.import_module(f'plugins.installed.{channel}.services.mapping')
            settings_mod = importlib.import_module(f'plugins.installed.{channel}.services.settings')
            fs = getattr(settings_mod, factory)()
            # The item map_product builds for the book (it needs a cover image).
            base = {'id': 'FREE-FEED', 'title': 'Free Feed', 'price': '8.50 USD'}
            items = mapping.expand_variants(self.book, base, fs)
            self.assertEqual([i['id'] for i in items], ['free-feed-print'], channel)
            self.assertEqual(items[0]['price'], '8.50 USD', channel)
