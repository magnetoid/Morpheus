"""dot_books shows a book with a free PDF at its printed price (owner, 2026-11-07).

The owner's choice: the card keeps the print price and says "Free PDF"; on the
book's page the PDF edition says Free, and the page opens on the printed
edition, so the price above the editions is the one selected.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from themes.test_head_contract import _activate_theme


class DotBooksFreePdfTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.book_product.models import BookProduct
        from plugins.installed.catalog.models import Product, ProductVariant

        cls.book = Product.objects.create(
            name='The Free Edition',
            slug='the-free-edition',
            sku='TFE',
            price=Money(Decimal('8.50'), 'USD'),
            product_type='variable',
            status='active',
        )
        BookProduct.objects.create(product=cls.book, author='Ada Writer', page_count=120)
        cls.pdf = ProductVariant.objects.create(
            product=cls.book,
            name='Digital PDF',
            sku='TFE-PDF',
            price=Money(0, 'USD'),
            variant_type='digital',
            requires_shipping=False,
            sort_order=0,
        )
        cls.printed = ProductVariant.objects.create(
            product=cls.book, name='Print', sku='TFE-P', variant_type='physical', sort_order=1
        )
        # A book whose only edition is a free PDF, its own price left at 8.50.
        cls.free_only = Product.objects.create(
            name='The Gift Book',
            slug='the-gift-book',
            sku='TGB',
            price=Money(Decimal('8.50'), 'USD'),
            product_type='variable',
            status='active',
        )
        BookProduct.objects.create(product=cls.free_only, author='Ada Writer', page_count=80)
        ProductVariant.objects.create(
            product=cls.free_only,
            name='Digital PDF',
            sku='TGB-PDF',
            price=Money(0, 'USD'),
            variant_type='digital',
            requires_shipping=False,
        )

    def setUp(self):
        _activate_theme(self, 'dot_books')

    def _get(self, path):
        resp = self.client.get(path)
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_the_card_keeps_the_print_price_and_says_free_pdf(self):
        html = self._get('/products/')
        start = html.index('href="/products/the-free-edition/"')
        # This card only: the page's empty cart elsewhere reads $0.00.
        card = html[start : html.index('class="book__actions"', start)]
        self.assertIn('<p class="book__formats">Print · Free PDF</p>', card)
        self.assertIn('<p class="price">$8.50</p>', card)

    def test_a_book_with_no_paid_edition_is_shown_free(self):
        html = self._get('/products/')
        start = html.index('href="/products/the-gift-book/"')
        card = html[start : html.index('class="book__actions"', start)]
        self.assertIn('<p class="book__formats">Free PDF</p>', card)
        self.assertIn('<p class="price">Free</p>', card)

    def test_the_pdf_says_free_and_the_page_opens_on_print(self):
        html = self._get('/products/the-free-edition/')
        pdf = html[html.index(f'data-variant-id="{self.pdf.pk}"') :][:1500]
        self.assertIn('data-variant-price="Free"', pdf)
        self.assertIn('<span class="pdp-variant__price">Free</span>', pdf)
        printed_at = html.index(f'data-variant-id="{self.printed.pk}"')
        button = html[html.rindex('<button', 0, printed_at) : printed_at]
        self.assertIn('is-selected', button)
        self.assertIn(f'name="variant_id" value="{self.printed.pk}"', html)
