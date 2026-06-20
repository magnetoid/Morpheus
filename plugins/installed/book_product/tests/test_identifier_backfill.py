"""Backfill matching logic + dashboard identifier save."""

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.management.commands.backfill_book_identifiers import pick_work


class PickWorkTests(TestCase):
    DOCS = [
        {
            'title': 'A Princess of Mars',
            'author_name': ['Edgar Rice Burroughs'],
            'key': '/works/OL1418187W',
            'oclc': ['34042251', '999'],
            'edition_count': 340,
        },
        {
            'title': 'A Princess of Mars / A Fighting Man of Mars',
            'author_name': ['Edgar Rice Burroughs'],
            'key': '/works/OL15638500W',
            'oclc': ['111'],
            'edition_count': 2,
        },
    ]

    def test_picks_highest_edition_count_match(self):
        olid, oclc = pick_work('A Princess of Mars', 'Edgar Rice Burroughs', self.DOCS)
        self.assertEqual(olid, 'OL1418187W')
        self.assertEqual(oclc, '34042251')

    def test_author_mismatch_rejected(self):
        olid, oclc = pick_work('A Princess of Mars', 'Jane Austen', self.DOCS)
        self.assertIsNone(olid)
        self.assertIsNone(oclc)

    def test_title_mismatch_rejected(self):
        olid, _ = pick_work('Pride and Prejudice', 'Edgar Rice Burroughs', self.DOCS)
        self.assertIsNone(olid)

    def test_no_oclc_returns_none_oclc(self):
        docs = [{'title': 'X', 'author_name': ['Y Z'], 'key': '/works/OL9W', 'edition_count': 1}]
        olid, oclc = pick_work('X', 'Y Z', docs)
        self.assertEqual(olid, 'OL9W')
        self.assertIsNone(oclc)


class DashboardIdentifierSaveTests(TestCase):
    def _product(self):
        from plugins.installed.catalog.models import Product

        return Product.objects.create(
            name='Utopia',
            slug='utopia',
            sku='BK-1',
            price=Money(Decimal('8.00'), 'USD'),
            product_type='simple',
            status='active',
        )

    def test_saves_and_clears_identifiers(self):
        from plugins.installed.book_product.dashboard import (
            _book_identifiers,
            save_book_fields,
        )
        from plugins.installed.book_product.models import BookProduct

        p = self._product()
        BookProduct.objects.create(product=p, author='Thomas More')

        save_book_fields(
            p,
            {
                'book_submitted': '1',
                'author': 'Thomas More',
                'isbn13': '9780140449105',
                'oclc': '34042251',
                'openlibrary': 'OL1418187W',
            },
        )
        ids = _book_identifiers(p)
        self.assertEqual(ids['isbn13'], '9780140449105')
        self.assertEqual(ids['oclc'], '34042251')
        self.assertEqual(ids['openlibrary'], 'OL1418187W')

        # Blank clears.
        save_book_fields(p, {'book_submitted': '1', 'author': 'Thomas More', 'isbn13': ''})
        self.assertEqual(_book_identifiers(p)['isbn13'], '')
