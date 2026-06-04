"""GraphQL control for Book Product — setBookProduct mutation + bookProduct query."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.book_product.graphql.inputs import BookProductInput
from plugins.installed.book_product.graphql.mutations import BookProductMutationExtension
from plugins.installed.book_product.graphql.queries import BookProductQueryExtension
from plugins.installed.book_product.models import BookProduct
from plugins.installed.catalog.models import Product


class _Info:
    """Minimal stand-in for strawberry.Info — only .context['request'] is read."""

    def __init__(self, *, staff: bool):
        req = RequestFactory().post('/graphql/')
        req.user = get_user_model().objects.create_user(
            username='gqlu', email='g@example.test', password='pw', is_staff=staff
        )
        self.context = {'request': req}


class BookProductGraphQLTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='GQL Book',
            slug='gql-book',
            sku='GQL-1',
            price=Money(Decimal('12.00'), 'USD'),
            product_type='simple',
        )

    def test_staff_can_set_then_query(self):
        info = _Info(staff=True)
        res = BookProductMutationExtension().set_book_product(
            info,
            BookProductInput(
                product_slug='gql-book',
                author='Ursula K. Le Guin',
                page_count=320,
                print_type='hardcover',
                publication_date='1974-05-01',
            ),
        )
        self.assertTrue(res.ok, res.error)
        self.assertTrue(BookProduct.objects.filter(product=self.product).exists())

        bt = BookProductQueryExtension().book_product(info, 'gql-book')
        self.assertEqual(bt.author, 'Ursula K. Le Guin')
        self.assertEqual(bt.page_count, 320)
        self.assertEqual(bt.print_type, 'hardcover')
        self.assertEqual(bt.publication_date, '1974-05-01')

    def test_non_staff_forbidden(self):
        res = BookProductMutationExtension().set_book_product(
            _Info(staff=False), BookProductInput(product_slug='gql-book', author='X')
        )
        self.assertFalse(res.ok)
        self.assertIn('staff', res.error.lower())
        self.assertFalse(BookProduct.objects.filter(product=self.product).exists())

    def test_invalid_print_type_rejected(self):
        res = BookProductMutationExtension().set_book_product(
            _Info(staff=True),
            BookProductInput(product_slug='gql-book', print_type='nonsense'),
        )
        self.assertFalse(res.ok)
        self.assertIn('print_type', res.error)

    def test_unknown_product(self):
        res = BookProductMutationExtension().set_book_product(
            _Info(staff=True), BookProductInput(product_slug='nope', author='X')
        )
        self.assertFalse(res.ok)
