"""The account's order history lists the customer's orders, dated.

Until v0.148.0 the view sorted on a ``created_at`` an order never had; the
FieldError was swallowed and every customer saw an empty history.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money


class OrderHistoryTests(TestCase):
    def test_history_lists_the_customers_orders_with_their_date(self):
        from plugins.installed.orders.models import Order

        me = get_user_model().objects.create_user(
            username='me@example.com', email='me@example.com', password='pw-1234!'
        )
        other = get_user_model().objects.create_user(
            username='other@example.com', email='other@example.com', password='pw-1234!'
        )
        mine = Order.objects.create(
            email='me@example.com', customer=me, subtotal=Money(8, 'USD'), total=Money(8, 'USD')
        )
        theirs = Order.objects.create(
            email='other@example.com',
            customer=other,
            subtotal=Money(5, 'USD'),
            total=Money(5, 'USD'),
        )
        self.client.force_login(me)
        body = self.client.get('/account/orders/').content.decode()
        self.assertIn(mine.order_number, body)
        self.assertNotIn(theirs.order_number, body)
        self.assertIn(str(mine.placed_at.year), body)
        detail = self.client.get(f'/account/orders/{mine.order_number}/').content.decode()
        self.assertIn(f'{mine.placed_at:%B} {mine.placed_at.day}, {mine.placed_at.year}', detail)
