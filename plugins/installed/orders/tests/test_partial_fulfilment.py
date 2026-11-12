"""An order ships in one parcel or several (``orders/fulfilment.py``).

Until v0.154.0 the fulfil form put every remaining unit into one parcel, so an
order could not leave in two boxes, and its tracking number was the order's.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class PartialFulfilmentTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product

        self.mug = Product.objects.create(
            name='Mug', slug='pf-mug', sku='PF-MUG', price=Money(5, 'USD')
        )
        self.lamp = Product.objects.create(
            name='Lamp', slug='pf-lamp', sku='PF-LAMP', price=Money(20, 'USD')
        )
        self.ebook = Product.objects.create(
            name='Guide',
            slug='pf-guide',
            sku='PF-PDF',
            product_type='digital',
            requires_shipping=False,
            price=Money(8, 'USD'),
        )

    def _order(self, *lines, status='processing'):
        from plugins.installed.orders.models import Order, OrderItem

        n = Order.objects.count()
        buyer = get_user_model().objects.create_user(
            username=f'pf{n}', email=f'pf{n}@example.com', password='x'
        )
        order = Order.objects.create(
            customer=buyer,
            email='buyer@example.com',
            subtotal=Money(30, 'USD'),
            total=Money(30, 'USD'),
            status=status,
            payment_status='paid',
        )
        items = []
        for product, qty in lines:
            items.append(
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    sku=product.sku,
                    quantity=qty,
                    unit_price=product.price,
                    total_price=product.price * qty,
                )
            )
        return order, items

    def _listen(self, event):
        seen = []

        def handler(**kwargs):
            seen.append(kwargs)

        hook_registry.register(event, handler, plugin=None)
        self.addCleanup(hook_registry.unregister, event, handler)
        return seen

    def _ship(self, order, lines=None, **kwargs):
        from plugins.installed.orders.fulfilment import create_fulfillment

        with self.captureOnCommitCallbacks(execute=True):
            return create_fulfillment(order, lines, **kwargs)

    def test_a_partial_parcel_leaves_the_rest_open(self):
        order, (mug, lamp) = self._order((self.mug, 2), (self.lamp, 1))
        created = self._listen(MorpheusEvents.FULFILLMENT_CREATED)
        fulfilled = self._listen(MorpheusEvents.ORDER_FULFILLED)

        parcel = self._ship(order, {str(mug.pk): 1}, tracking_number='TRK-1', carrier='DHL')

        self.assertEqual(order.status, 'partially_fulfilled')
        mug.refresh_from_db()
        self.assertEqual(mug.fulfilled_quantity, 1)
        self.assertEqual(
            [(fi.order_item_id, fi.quantity) for fi in parcel.items.all()], [(mug.pk, 1)]
        )
        self.assertEqual(parcel.tracking_number, 'TRK-1')
        self.assertEqual(len(created), 1)
        self.assertFalse(created[0]['complete'])
        self.assertEqual(fulfilled, [])
        self.assertEqual(order.events.filter(event_type='ORDER_PARTIALLY_FULFILLED').count(), 1)

    def test_the_last_parcel_ships_the_order_and_emails_once_per_box(self):
        order, (mug, lamp) = self._order((self.mug, 2), (self.lamp, 1))
        fulfilled = self._listen(MorpheusEvents.ORDER_FULFILLED)

        self._ship(order, {str(mug.pk): 2}, tracking_number='TRK-A')
        self._ship(order, {str(lamp.pk): 1}, tracking_number='TRK-B')

        self.assertEqual(order.status, 'shipped')
        self.assertEqual(order.tracking_number, 'TRK-B')
        self.assertEqual(len(fulfilled), 1)
        subjects = [m.subject for m in mail.outbox]
        self.assertEqual(sum('Part of order' in s for s in subjects), 1)
        self.assertEqual(sum(s.startswith('Order #') and 'on its way' in s for s in subjects), 1)
        part = next(m for m in mail.outbox if 'Part of order' in m.subject)
        self.assertIn('TRK-A', part.body)
        self.assertIn('Mug', part.body)
        self.assertNotIn('Lamp', part.body)

    def test_the_last_parcel_left_unshipped_quotes_its_own_tracking(self):
        order, (mug, lamp) = self._order((self.mug, 2), (self.lamp, 1))
        self._ship(order, {str(mug.pk): 2}, tracking_number='TRK-A')
        mail.outbox.clear()

        self._ship(order, {str(lamp.pk): 1}, tracking_number='TRK-B', mark_shipped=False)

        self.assertEqual(order.status, 'fulfilled')
        (email,) = mail.outbox
        self.assertEqual(email.subject, f'Order #{order.order_number} is on its way')
        self.assertIn('TRK-B', email.body)
        self.assertNotIn('TRK-A', email.body)

    def test_a_last_parcel_without_tracking_never_quotes_an_earlier_box(self):
        order, (mug, lamp) = self._order((self.mug, 2), (self.lamp, 1))
        self._ship(order, {str(mug.pk): 2}, tracking_number='TRK-A')
        mail.outbox.clear()

        self._ship(order, {str(lamp.pk): 1})

        self.assertEqual(order.status, 'shipped')
        self.assertEqual(order.tracking_number, '')
        (email,) = mail.outbox
        self.assertNotIn('TRK-A', email.body)

    def test_an_order_fulfilled_without_a_parcel_still_hears_of_its_parcel(self):
        # GraphQL's markOrderFulfilled leaves an order fulfilled with no parcel;
        # shipping it from there fires no ORDER_FULFILLED, so the parcel's own
        # email is the only one the buyer gets.
        order, _items = self._order((self.mug, 1), status='fulfilled')

        self._ship(order, tracking_number='TRK-F')

        self.assertEqual(order.status, 'shipped')
        (email,) = mail.outbox
        self.assertEqual(email.subject, f'Order #{order.order_number} is on its way')
        self.assertIn('TRK-F', email.body)
        self.assertIn('last parcel', email.body)

    def test_leaving_mark_shipped_off_fulfils_without_shipping(self):
        order, _items = self._order((self.mug, 1))
        self._ship(order, mark_shipped=False)
        self.assertEqual(order.status, 'fulfilled')

    def test_downloads_never_go_in_a_parcel(self):
        from plugins.installed.orders.fulfilment import FulfilmentError, is_complete

        order, (mug, ebook) = self._order((self.mug, 1), (self.ebook, 1))
        with self.assertRaisesMessage(FulfilmentError, 'not open'):
            self._ship(order, {str(ebook.pk): 1})
        self._ship(order)
        self.assertTrue(is_complete(order))
        self.assertEqual(order.status, 'shipped')
        ebook.refresh_from_db()
        self.assertEqual(ebook.fulfilled_quantity, 0)

        only_downloads, _ = self._order((self.ebook, 1))
        with self.assertRaisesMessage(FulfilmentError, 'Nothing in this order is left to ship'):
            self._ship(only_downloads)

    def test_quantities_are_checked(self):
        from plugins.installed.orders.fulfilment import FulfilmentError

        order, (mug,) = self._order((self.mug, 2))
        for lines, message in (
            ({str(mug.pk): 3}, 'Only 2 of "Mug" are left to ship'),
            ({str(mug.pk): -1}, 'cannot be negative'),
            ({str(mug.pk): 'two'}, 'whole number'),
            ({str(mug.pk): 0}, 'at least one unit'),
            ({'00000000-0000-0000-0000-000000000000': 1}, 'not open'),
        ):
            with self.subTest(lines=lines), self.assertRaisesMessage(FulfilmentError, message):
                self._ship(order, lines)
        self.assertFalse(order.fulfillments.exists())
        self.assertEqual(order.status, 'processing')

    def test_a_pending_order_walks_forward(self):
        order, _items = self._order((self.mug, 1), status='pending')
        self._ship(order)
        self.assertEqual(order.status, 'shipped')

    def test_a_cancelled_order_cannot_ship(self):
        from plugins.installed.orders.fulfilment import FulfilmentError

        order, _items = self._order((self.mug, 1), status='cancelled')
        with self.assertRaisesMessage(FulfilmentError, 'cannot ship a parcel'):
            self._ship(order)

    def test_a_stale_order_is_refused(self):
        from plugins.installed.orders.fulfilment import FulfilmentError
        from plugins.installed.orders.models import Order

        order, (mug,) = self._order((self.mug, 2))
        stale = Order.objects.get(pk=order.pk)
        self._ship(order, {str(mug.pk): 1})
        with self.assertRaisesMessage(FulfilmentError, 'changed meanwhile'):
            self._ship(stale, {str(mug.pk): 1})
        mug.refresh_from_db()
        self.assertEqual(mug.fulfilled_quantity, 1)

    def test_an_overlong_tracking_url_is_dropped_not_cut(self):
        order, _items = self._order((self.mug, 1))
        parcel = self._ship(
            order, tracking_number='T', tracking_url='https://track.example/' + 'x' * 300
        )
        self.assertEqual(parcel.tracking_url, '')


class FulfillLinesToolTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product
        from plugins.installed.orders.models import Order, OrderItem

        mug = Product.objects.create(name='Mug', slug='fl-mug', sku='FL-MUG', price=Money(5, 'USD'))
        self.order = Order.objects.create(
            email='b@example.com',
            subtotal=Money(10, 'USD'),
            total=Money(10, 'USD'),
            status='processing',
            payment_status='paid',
        )
        OrderItem.objects.create(
            order=self.order,
            product=mug,
            product_name='Mug',
            sku='FL-MUG',
            quantity=2,
            unit_price=Money(5, 'USD'),
            total_price=Money(10, 'USD'),
        )

    def _call(self, **kwargs):
        from plugins.installed.orders.agent_tools import orders_fulfill_lines_tool

        return orders_fulfill_lines_tool.invoke(kwargs)

    def test_ships_by_sku_and_reports_what_is_left(self):
        result = self._call(
            order_number=self.order.order_number,
            lines=[{'sku': 'fl-mug', 'quantity': 1}],
            tracking_number='TRK',
        )
        self.assertEqual(result.output['status'], 'partially_fulfilled')
        self.assertEqual(result.output['units_left_to_ship'], 1)
        self.assertEqual(result.output['parcel'], [{'sku': 'FL-MUG', 'name': 'Mug', 'quantity': 1}])

    def test_an_unknown_sku_is_refused(self):
        from morpheus.core import ToolError

        with self.assertRaisesMessage(ToolError, 'no open line'):
            self._call(order_number=self.order.order_number, lines=[{'sku': 'nope', 'quantity': 1}])

    def test_the_tool_needs_approval(self):
        from plugins.installed.orders.agent_tools import orders_fulfill_lines_tool

        self.assertTrue(orders_fulfill_lines_tool.requires_approval)
        self.assertEqual(orders_fulfill_lines_tool.scopes, ['orders.write'])
