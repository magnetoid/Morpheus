"""recompute_copurchases counts every canonical paid status (autopilot-plan
Phase-1 follow-up): the old hardcoded tuple included statuses that don't
exist on the Order FSM ('paid'/'completed') and missed processing/shipped/
delivered orders — silently under-counting co-purchases."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Order, OrderItem
from plugins.installed.personalisation.models import CoPurchaseScore
from plugins.installed.personalisation.services import MIN_CO_COUNT, recompute_copurchases


def _product(slug, sku):
    return Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=sku,
        price=Money(Decimal('10.00'), 'USD'),
        product_type='simple',
        status='active',
    )


def _order_with(products, *, status):
    order = Order.objects.create(
        email='b@x.io',
        subtotal=Money(Decimal('10.00'), 'USD'),
        total=Money(Decimal('10.00'), 'USD'),
    )
    # status is a protected FSMField — set the state via update().
    Order.objects.filter(pk=order.pk).update(status=status)
    for p in products:
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


class CoPurchaseStatusTests(TestCase):
    def test_delivered_orders_count_and_cancelled_do_not(self):
        a, b, c = _product('a', 'A'), _product('b', 'B'), _product('c', 'C')
        for _ in range(MIN_CO_COUNT):
            _order_with([a, b], status='delivered')  # previously MISSED
            _order_with([a, c], status='cancelled')  # must never count
        recompute_copurchases()
        self.assertTrue(CoPurchaseScore.objects.filter(anchor=a, related=b).exists())
        self.assertFalse(CoPurchaseScore.objects.filter(anchor=a, related=c).exists())
