"""Which order lines a customer may return (C4, v0.188.0).

A line comes back only when its order is paid, it ships, its units are in a parcel
whose return window is open, and no open or finished return already holds them.
"""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Fulfillment, FulfillmentItem, Order, OrderItem
from plugins.installed.orders.refunds import ReturnRequest, ReturnService


def _usd(n):
    return Money(n, 'USD')


class _Base(TestCase):
    def setUp(self):
        self.lamp = Product.objects.create(
            name='Zephyr Lamp', slug='zephyr-lamp', sku='ZL', price=10
        )
        self.ebook = Product.objects.create(
            name='Quillon Ebook',
            slug='quillon-ebook',
            sku='QE',
            price=10,
            product_type='digital',
            requires_shipping=False,
        )

    def order(self, *, payment_status='paid', metadata=None, lines=None):
        order = Order.objects.create(
            email='buyer@example.com',
            subtotal=_usd(20),
            total=_usd(20),
            payment_status=payment_status,
            metadata=metadata or {},
        )
        for product, qty in lines or [(self.lamp, 1)]:
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                quantity=qty,
                unit_price=_usd(10),
                total_price=_usd(10 * qty),
            )
        return order

    def ship(self, order, item, units, *, delivered_days_ago=None, shipped_days_ago=1):
        now = timezone.now()
        parcel = Fulfillment.objects.create(
            order=order,
            shipped_at=now - timedelta(days=shipped_days_ago),
            delivered_at=(
                now - timedelta(days=delivered_days_ago) if delivered_days_ago is not None else None
            ),
        )
        FulfillmentItem.objects.create(fulfillment=parcel, order_item=item, quantity=units)
        return parcel

    def lines(self, order, window=30):
        from plugins.installed.orders.returns import returnable_lines

        return {str(line.item.pk): line for line in returnable_lines(order, window_days=window)}


class ReturnableLinesTests(_Base):
    def test_unpaid_order_has_nothing_to_return(self):
        order = self.order(payment_status='unpaid')
        item = order.items.get()
        self.ship(order, item, 1)
        line = self.lines(order)[str(item.pk)]
        self.assertEqual((line.units, line.reason), (0, 'not_paid'))

    def test_download_line_never_returns(self):
        order = self.order(lines=[(self.ebook, 1)])
        line = self.lines(order)[str(order.items.get().pk)]
        self.assertEqual((line.units, line.reason), (0, 'does_not_ship'))

    def test_unsent_units_are_not_returnable_but_sent_ones_are(self):
        order = self.order(lines=[(self.lamp, 2)])
        item = order.items.get()
        self.assertEqual(self.lines(order)[str(item.pk)].reason, 'not_sent')
        self.ship(order, item, 1)
        line = self.lines(order)[str(item.pk)]
        self.assertEqual((line.units, line.reason), (1, ''))

    def test_a_parcel_recorded_but_not_yet_sent_does_not_count(self):
        order = self.order()
        item = order.items.get()
        parcel = Fulfillment.objects.create(order=order, status='pending')
        FulfillmentItem.objects.create(fulfillment=parcel, order_item=item, quantity=1)
        self.assertEqual(self.lines(order)[str(item.pk)].reason, 'not_sent')

    def test_window_counts_from_the_parcels_delivery(self):
        order = self.order()
        item = order.items.get()
        parcel = self.ship(order, item, 1, delivered_days_ago=10, shipped_days_ago=12)
        line = self.lines(order, window=7)[str(item.pk)]
        self.assertEqual((line.units, line.reason), (0, 'window_closed'))
        line = self.lines(order, window=30)[str(item.pk)]
        self.assertEqual(line.units, 1)
        self.assertEqual(line.window_ends, (parcel.delivered_at + timedelta(days=30)).date())

    def test_parcel_without_delivery_gets_the_transit_allowance(self):
        from plugins.installed.orders.returns import parcel_start
        from plugins.installed.orders.withdrawal import TRANSIT_ALLOWANCE_DAYS

        order = self.order()
        parcel = self.ship(order, order.items.get(), 1, shipped_days_ago=2)
        self.assertEqual(
            parcel_start(parcel), parcel.shipped_at + timedelta(days=TRANSIT_ALLOWANCE_DAYS)
        )

    def test_units_in_an_open_return_are_held(self):
        order = self.order(lines=[(self.lamp, 2)])
        item = order.items.get()
        self.ship(order, item, 2)
        ReturnRequest.objects.create(
            order=order, items=[{'order_item_id': str(item.pk), 'quantity': 2}]
        )
        line = self.lines(order)[str(item.pk)]
        self.assertEqual((line.units, line.reason), (0, 'already_returned'))

    def test_rejected_return_releases_its_units(self):
        order = self.order()
        item = order.items.get()
        self.ship(order, item, 1)
        ReturnRequest.objects.create(
            order=order, state='rejected', items=[{'order_item_id': str(item.pk), 'quantity': 1}]
        )
        self.assertEqual(self.lines(order)[str(item.pk)].units, 1)

    def test_exchange_order_is_not_returnable(self):
        order = self.order(metadata={'exchange_of': 'RMA-1'})
        item = order.items.get()
        self.ship(order, item, 1)
        line = self.lines(order)[str(item.pk)]
        self.assertEqual((line.units, line.reason), (0, 'exchange_order'))

    def test_no_window_means_nothing_returns(self):
        order = self.order()
        item = order.items.get()
        self.ship(order, item, 1)
        self.assertEqual(self.lines(order, window=0)[str(item.pk)].reason, 'window_closed')


class CreateRequestGuardTests(_Base):
    def test_second_request_for_the_last_unit_is_refused(self):
        from plugins.installed.orders.returns import ReturnRefused

        order = self.order()
        item = order.items.get()
        self.ship(order, item, 1)
        items = [{'order_item_id': str(item.pk), 'quantity': 1}]
        ReturnService.create_request(order=order, items=items, window_days=30)
        with self.assertRaises(ReturnRefused):
            ReturnService.create_request(order=order, items=items, window_days=30)
        self.assertEqual(ReturnRequest.objects.filter(order=order).count(), 1)

    def test_more_units_than_sent_are_refused(self):
        from plugins.installed.orders.returns import ReturnRefused

        order = self.order(lines=[(self.lamp, 2)])
        item = order.items.get()
        self.ship(order, item, 1)
        with self.assertRaises(ReturnRefused):
            ReturnService.create_request(
                order=order,
                items=[{'order_item_id': str(item.pk), 'quantity': 2}],
                window_days=30,
            )

    def test_staff_request_without_window_is_unchanged(self):
        order = self.order(payment_status='unpaid')
        item = order.items.get()
        rr = ReturnService.create_request(
            order=order, items=[{'order_item_id': str(item.pk), 'quantity': 1}]
        )
        self.assertEqual(rr.state, 'requested')
