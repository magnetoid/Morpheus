"""The review-request email deep-links to each book's review form."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Order, OrderItem
from plugins.installed.post_purchase.tasks import _review_links


def _order_with_books(*names):
    order = Order.objects.create(
        email='reader@example.com',
        subtotal=Money(Decimal('20'), 'USD'),
        total=Money(Decimal('20'), 'USD'),
    )
    for i, name in enumerate(names):
        p = Product.objects.create(
            name=name, slug=f'book-{i}', sku=f'SKU{i}', price=Money(Decimal('20'), 'USD')
        )
        OrderItem.objects.create(
            order=order,
            product=p,
            product_name=p.name,
            sku=p.sku,
            quantity=1,
            unit_price=p.price,
            total_price=p.price,
        )
    return order


class ReviewLinksTests(TestCase):
    def test_one_line_per_book_with_review_url(self):
        order = _order_with_books('Giants Bread', 'The Blue Castle')
        out = _review_links(order)
        lines = [ln for ln in out.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 2)
        self.assertIn('Giants Bread', out)
        self.assertIn('The Blue Castle', out)
        # deep-links to the reviews:add form for each product
        self.assertEqual(out.count('/reviews/add/'), 2)

    def test_empty_order_returns_empty_string(self):
        order = Order.objects.create(
            email='x@example.com',
            subtotal=Money(Decimal('0'), 'USD'),
            total=Money(Decimal('0'), 'USD'),
        )
        self.assertEqual(_review_links(order), '')
