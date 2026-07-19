"""Regression tests for refund proration of the order-level discount (Fix 4).

``ReturnService._compute_refund`` used to sum pre-discount ``unit_price*qty``
and ignore ``Order.discount_total`` → it over-refunded discounted orders
(store credit over-issued; a full money refund blocked by the over-refund
ceiling). It now subtracts the returned lines' proportional share of
``order.discount_total`` (scaled by their share of ``order.subtotal``) and
clamps the result to ``order.total − already-processed refunds``.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.orders.models import Order, OrderItem, Refund
from plugins.installed.orders.refunds import ReturnService
from plugins.installed.orders.tests.test_refunds import _setup_order


def _usd(n):
    return Money(Decimal(str(n)), 'USD')


def _make_order(*, subtotal, discount_total, total):
    return Order.objects.create(
        email='c@example.com',
        subtotal=_usd(subtotal),
        discount_total=_usd(discount_total),
        total=_usd(total),
    )


def _add_item(order, unit_price, qty=1):
    return OrderItem.objects.create(
        order=order,
        product_name='Book',
        sku='B',
        quantity=qty,
        unit_price=_usd(unit_price),
        total_price=_usd(Decimal(str(unit_price)) * qty),
    )


def _return(order, *lines):
    """lines = (order_item, quantity) tuples."""
    return ReturnService.create_request(
        order=order,
        items=[{'order_item_id': str(it.id), 'quantity': q} for it, q in lines],
    )


class RefundDiscountProrationTests(TestCase):
    def test_full_return_of_discounted_order_equals_order_total(self):
        # 1 item @ $100, subtotal $100, $50 discount, total $50.
        # gross 100 − prorated discount 50*(100/100) = 50 (NOT the raw $100).
        order = _make_order(subtotal='100', discount_total='50', total='50')
        item = _add_item(order, '100', qty=1)
        rr = _return(order, (item, 1))

        amount = ReturnService._compute_refund(rr)

        self.assertEqual(amount.amount, Decimal('50.00'))

    def test_non_discounted_order_refunds_full_line_price(self):
        # Regression guard: the fix must not change the no-discount case.
        # _setup_order builds subtotal==total, discount_total defaulting to 0.
        order, item = _setup_order(amount='25', qty=2)  # subtotal==total==50
        rr = _return(order, (item, 2))

        amount = ReturnService._compute_refund(rr)

        self.assertEqual(amount.amount, Decimal('50.00'))

    def test_partial_return_of_discounted_order_prorates_share(self):
        # 2 items @ $50 (subtotal $100), $40 discount, total $60. Return one.
        # 50 − 40*(50/100) = 30 (NOT the raw $50).
        order = _make_order(subtotal='100', discount_total='40', total='60')
        item_a = _add_item(order, '50', qty=1)
        _add_item(order, '50', qty=1)
        rr = _return(order, (item_a, 1))

        amount = ReturnService._compute_refund(rr)

        self.assertEqual(amount.amount, Decimal('30.00'))

    def test_refund_clamped_to_remaining_after_prior_refund(self):
        # $100 order, no discount, with an $80 already-processed refund.
        # gross 100 clamps to total(100) − already(80) = 20.
        order = _make_order(subtotal='100', discount_total='0', total='100')
        item = _add_item(order, '100', qty=1)
        Refund.objects.create(order=order, amount=_usd(80), is_processed=True)
        rr = _return(order, (item, 1))

        amount = ReturnService._compute_refund(rr)

        self.assertEqual(amount.amount, Decimal('20.00'))
