"""Orders' parcel settings (v0.155.0): ``parcel_emails`` and ``fulfil_marks_shipped``.

v0.154.0 emailed every parcel and shipped an order with its last parcel, with no
way for a merchant to choose otherwise.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.registry import app_registry


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class ParcelSettingsTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product

        self.orders = app_registry.get('orders')
        self.addCleanup(self.orders.invalidate_config_cache)
        self.mug = Product.objects.create(
            name='Mug', slug='ps-mug', sku='PS-MUG', price=Money(5, 'USD')
        )
        self.lamp = Product.objects.create(
            name='Lamp', slug='ps-lamp', sku='PS-LAMP', price=Money(20, 'USD')
        )

    def _order(self):
        from plugins.installed.orders.models import Order, OrderItem

        buyer = get_user_model().objects.create_user(
            username=f'ps{Order.objects.count()}',
            email=f'ps{Order.objects.count()}@example.com',
            password='x',
        )
        order = Order.objects.create(
            customer=buyer,
            email='buyer@example.com',
            subtotal=Money(25, 'USD'),
            total=Money(25, 'USD'),
            status='processing',
            payment_status='paid',
        )
        items = [
            OrderItem.objects.create(
                order=order,
                product=p,
                product_name=p.name,
                sku=p.sku,
                quantity=1,
                unit_price=p.price,
                total_price=p.price,
            )
            for p in (self.mug, self.lamp)
        ]
        return order, items

    def _ship(self, order, lines=None, **kwargs):
        from plugins.installed.orders.fulfilment import create_fulfillment

        with self.captureOnCommitCallbacks(execute=True):
            return create_fulfillment(order, lines, **kwargs)

    def test_when_complete_sends_one_email_listing_every_parcel(self):
        self.orders.set_config('parcel_emails', 'when_complete')
        order, (mug, lamp) = self._order()
        self._ship(order, {str(mug.pk): 1}, tracking_number='TRK-A', carrier='DHL')
        self.assertEqual(mail.outbox, [])
        self._ship(order, {str(lamp.pk): 1}, tracking_number='TRK-B')
        (email,) = mail.outbox
        self.assertIn('is on its way', email.subject)
        for text in ('TRK-A', 'TRK-B', 'Mug', 'Lamp', 'Parcel 2'):
            self.assertIn(text, email.body)

    def test_when_complete_keeps_the_one_email_of_a_single_parcel(self):
        self.orders.set_config('parcel_emails', 'when_complete')
        order, _ = self._order()
        self._ship(order, tracking_number='TRK-1')
        (email,) = mail.outbox
        self.assertIn('TRK-1', email.body)
        self.assertNotIn('Parcel 1', email.body)

    def test_each_parcel_is_the_default(self):
        order, (mug, lamp) = self._order()
        self._ship(order, {str(mug.pk): 1}, tracking_number='TRK-A')
        self._ship(order, {str(lamp.pk): 1}, tracking_number='TRK-B')
        self.assertEqual(len(mail.outbox), 2)

    def test_the_last_parcel_may_leave_the_order_fulfilled(self):
        from plugins.installed.admin_dashboard.forms.orders import FulfillmentForm
        from plugins.installed.orders.agent_tools import orders_fulfill_lines_tool

        self.assertTrue(FulfillmentForm(order=self._order()[0]).fields['mark_shipped'].initial)
        self.orders.set_config('fulfil_marks_shipped', False)
        order, _ = self._order()
        self.assertFalse(FulfillmentForm(order=order).fields['mark_shipped'].initial)
        with self.captureOnCommitCallbacks(execute=True):
            result = orders_fulfill_lines_tool.invoke({'order_number': order.order_number})
        self.assertEqual(result.output['status'], 'fulfilled')
        order, _ = self._order()
        with self.captureOnCommitCallbacks(execute=True):
            result = orders_fulfill_lines_tool.invoke(
                {'order_number': order.order_number, 'mark_shipped': True}
            )
        self.assertEqual(result.output['status'], 'shipped')
