"""Marketplace order-splitting tests."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, Vendor
from plugins.installed.marketplace.models import VendorOrder, VendorPayoutAccount
from plugins.installed.marketplace.services import split_order
from plugins.installed.orders.models import Order, OrderItem


class MarketplaceSplitTests(TestCase):
    def test_split_order_creates_vendor_orders_with_commission(self):
        vendor = Vendor.objects.create(
            name='Vendor A',
            slug='vendor-a',
            commission_rate=Decimal('20'),
        )
        product = Product.objects.create(
            name='Widget',
            slug='widget',
            sku='W1',
            price=Money(50, 'USD'),
            status='active',
            vendor=vendor,
        )
        order = Order.objects.create(
            email='buyer@example.com',
            subtotal=Money(100, 'USD'),
            total=Money(100, 'USD'),
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name='Widget',
            quantity=2,
            unit_price=Money(50, 'USD'),
            total_price=Money(100, 'USD'),
        )

        vorders = split_order(order)
        self.assertEqual(len(vorders), 1)
        v = vorders[0]
        self.assertEqual(v.gross.amount, Decimal('100.00'))
        self.assertEqual(v.commission.amount, Decimal('20.00'))
        self.assertEqual(v.net.amount, Decimal('80.00'))
        # And the vendor's payout account was credited.
        acct = VendorPayoutAccount.objects.get(vendor=vendor)
        self.assertEqual(acct.accrued_balance.amount, Decimal('80.00'))

    def test_split_order_is_idempotent(self):
        vendor = Vendor.objects.create(name='V', slug='v', commission_rate=Decimal('0'))
        product = Product.objects.create(
            name='P',
            slug='p',
            sku='P1',
            price=Money(10, 'USD'),
            status='active',
            vendor=vendor,
        )
        order = Order.objects.create(
            email='b@example.com',
            subtotal=Money(10, 'USD'),
            total=Money(10, 'USD'),
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name='P',
            quantity=1,
            unit_price=Money(10, 'USD'),
            total_price=Money(10, 'USD'),
        )
        split_order(order)
        split_order(order)
        self.assertEqual(VendorOrder.objects.filter(parent_order=order).count(), 1)
