"""PDP Book JSON-LD assembly — the deferred-field contract test.

Regression guard for the incident where feeding structured-data builders a
``.only()``-loaded Product 500'd on the deferred ``price`` (djmoney KeyError).
``_book_jsonld_data`` must assemble the Book dict from SAFE sources only
(relation queries by PK + the GraphQL dict's price), never the deferred field —
so we load product_row with the EXACT ``.only(...)`` the view uses and assert it
neither crashes nor touches ``.price``.
"""

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.storefront.views.catalog import _book_jsonld_data, _product_codes


def _deferred_row(slug):
    """Reload exactly as product_detail() does — price is deferred."""
    return Product.objects.filter(slug=slug).only('id', 'slug', 'updated_at').first()


class PdpBookJsonldDataTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Utopia',
            slug='utopia',
            sku='BK-1',
            price=Money(Decimal('8.00'), 'USD'),
            product_type='simple',
            status='active',
        )
        from plugins.installed.book_product.models import BookProduct

        BookProduct.objects.create(
            product=self.product,
            author='Thomas More',
            print_type='paperback',
            language='en',
        )
        # ISBN lives in the identifiers metafield namespace.
        try:
            from plugins.installed.metafields.models import Metafield

            Metafield.objects.set_for(self.product, 'identifiers.isbn13', '9780140449105')
        except Exception:  # noqa: BLE001 — set_for signature drift shouldn't fail the suite
            pass

    def test_assembles_without_touching_deferred_price(self):
        row = _deferred_row('utopia')
        product_dict = {
            'name': 'Utopia',
            'slug': 'utopia',
            'price': {'amount': '8.00', 'currency': 'USD'},
        }
        # Must NOT raise (the old code did, on row.price).
        data = _book_jsonld_data(row, product_dict, _product_codes(row), False)
        self.assertIsNotNone(data)
        self.assertEqual(data['authors'], ['Thomas More'])
        self.assertEqual(data['book_format'], 'paperback')
        self.assertEqual(data['price'], '8.00')

    def test_renders_book_jsonld_end_to_end(self):
        from plugins.installed.seo.services import book_jsonld

        row = _deferred_row('utopia')
        product_dict = {
            'name': 'Utopia',
            'slug': 'utopia',
            'price': {'amount': '8.00', 'currency': 'USD'},
        }
        data = _book_jsonld_data(row, product_dict, _product_codes(row), False)
        out = book_jsonld(data, base_url='https://shop.test/')
        self.assertEqual(out['@type'], 'Book')
        self.assertEqual(out['workExample']['bookFormat'], 'https://schema.org/Paperback')
        self.assertEqual(
            out['workExample']['potentialAction']['expectsAcceptanceOf']['price'], '8.00'
        )

    def test_non_book_product_returns_none(self):
        Product.objects.create(
            name='Mug',
            slug='mug',
            sku='MUG-1',
            price=Money(Decimal('5.00'), 'USD'),
            product_type='simple',
            status='active',
        )
        row = _deferred_row('mug')
        data = _book_jsonld_data(row, {'name': 'Mug', 'slug': 'mug'}, _product_codes(row), False)
        self.assertIsNone(data)
