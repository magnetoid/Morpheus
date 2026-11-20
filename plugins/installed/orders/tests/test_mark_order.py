"""Marking an order fulfilled or shipped records the parcel (``orders/fulfilment.py:mark_order``).

Until v0.182.0 Linda's ``orders.mark_fulfilled`` / ``orders.mark_shipped`` and GraphQL
``markOrderFulfilled`` / ``markOrderShipped`` moved the status alone: the order said
fulfilled while none of its lines had left, so a later parcel, a return or the
withdrawal period read it wrong.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from djmoney.money import Money


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class MarkOrderTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product

        self.mug = Product.objects.create(
            name='Mug', slug='mo-mug', sku='MO-MUG', price=Money(5, 'USD')
        )
        self.ebook = Product.objects.create(
            name='Guide',
            slug='mo-guide',
            sku='MO-PDF',
            product_type='digital',
            requires_shipping=False,
            price=Money(8, 'USD'),
        )

    def _order(self, *lines, status='processing'):
        from plugins.installed.orders.models import Order, OrderItem

        order = Order.objects.create(
            email='buyer@example.com',
            subtotal=Money(10, 'USD'),
            total=Money(10, 'USD'),
            status=status,
            payment_status='paid',
        )
        for product, qty in lines:
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                sku=product.sku,
                quantity=qty,
                unit_price=product.price,
                total_price=product.price * qty,
            )
        return order

    def _tool(self, name, **args):
        from core.agents.registry import agent_registry

        with self.captureOnCommitCallbacks(execute=True):
            return agent_registry.get_tool(name).invoke(args)

    def _fresh(self, order):
        from plugins.installed.orders.models import Order

        return Order.objects.get(pk=order.pk)

    def test_marking_fulfilled_records_a_parcel_with_every_unit(self):
        order = self._order((self.mug, 2), (self.ebook, 1))
        self._tool('orders.mark_fulfilled', order_number=order.order_number)
        order = self._fresh(order)
        self.assertEqual(order.status, 'fulfilled')
        (parcel,) = order.fulfillments.all()
        # The download never goes in a box.
        self.assertEqual(
            [(fi.order_item.sku, fi.quantity) for fi in parcel.items.all()], [('MO-MUG', 2)]
        )

    def test_marking_shipped_records_the_parcel_with_its_tracking(self):
        order = self._order((self.mug, 1))
        self._tool('orders.mark_shipped', order_number=order.order_number, tracking_number='TRK-9')
        order = self._fresh(order)
        self.assertEqual(order.status, 'shipped')
        self.assertEqual(order.fulfillments.get().tracking_number, 'TRK-9')

    def test_shipping_an_order_whose_units_are_all_in_parcels_adds_no_parcel(self):
        from plugins.installed.orders.fulfilment import create_fulfillment

        order = self._order((self.mug, 1))
        with self.captureOnCommitCallbacks(execute=True):
            create_fulfillment(order, None, mark_shipped=False)
        self.assertEqual(self._fresh(order).status, 'fulfilled')
        self._tool('orders.mark_shipped', order_number=order.order_number, tracking_number='TRK-2')
        order = self._fresh(order)
        self.assertEqual(order.status, 'shipped')
        self.assertEqual(order.fulfillments.count(), 1)
        self.assertEqual(order.tracking_number, 'TRK-2')

    def test_an_order_fulfilled_without_a_parcel_gets_one_when_shipped(self):
        # How markOrderFulfilled left orders before v0.182.0.
        order = self._order((self.mug, 1), status='fulfilled')
        self._tool('orders.mark_shipped', order_number=order.order_number)
        order = self._fresh(order)
        self.assertEqual(order.status, 'shipped')
        self.assertEqual(order.fulfillments.get().items.get().quantity, 1)

    def test_an_unpaid_order_is_not_walked_forward(self):
        from core.agents.tools import ToolError

        order = self._order((self.mug, 1), status='pending')
        for name in ('orders.mark_fulfilled', 'orders.mark_shipped'):
            with self.subTest(tool=name), self.assertRaises(ToolError):
                self._tool(name, order_number=order.order_number)
        self.assertEqual(self._fresh(order).status, 'pending')
        self.assertFalse(order.fulfillments.exists())

    def test_an_order_with_nothing_that_ships_is_refused(self):
        from core.agents.tools import ToolError

        order = self._order((self.ebook, 1))
        with self.assertRaises(ToolError) as caught:
            self._tool('orders.mark_fulfilled', order_number=order.order_number)
        self.assertIn('download', str(caught.exception))
        self.assertEqual(self._fresh(order).status, 'processing')


class GraphQLMarkOrderTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product
        from plugins.installed.orders.models import Order, OrderItem

        staff = get_user_model().objects.create_user(
            username='mo-staff', email='mo@example.test', password='x', is_staff=True
        )
        self.client.force_login(staff)
        mug = Product.objects.create(name='Mug', slug='gq-mug', sku='GQ-MUG', price=Money(5, 'USD'))
        self.order = Order.objects.create(
            email='buyer@example.com',
            subtotal=Money(5, 'USD'),
            total=Money(5, 'USD'),
            status='processing',
            payment_status='paid',
        )
        OrderItem.objects.create(
            order=self.order,
            product=mug,
            product_name='Mug',
            sku='GQ-MUG',
            quantity=1,
            unit_price=mug.price,
            total_price=mug.price,
        )

    def _mutate(self, name, extra=''):
        query = (
            f'mutation {{ {name}(input: {{orderNumber: "{self.order.order_number}"{extra}}}) '
            '{ status error } }'
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                '/graphql/', json.dumps({'query': query}), content_type='application/json'
            )
        return response.json()['data'][name]

    def test_mark_order_fulfilled_records_the_parcel(self):
        data = self._mutate('markOrderFulfilled')
        self.assertEqual(data['status'], 'fulfilled', data)
        self.assertEqual(self.order.fulfillments.count(), 1)

    def test_mark_order_shipped_records_the_parcel(self):
        data = self._mutate('markOrderShipped', ', trackingNumber: "TRK-G"')
        self.assertEqual(data['status'], 'shipped', data)
        self.assertEqual(self.order.fulfillments.get().tracking_number, 'TRK-G')
