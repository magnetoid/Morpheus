"""The order page's Cancel and the bulk cancel go through orders' one cancel
rule (v0.180.0): a shipped order is refused, and staff_cancel_refund decides
whether a paid order is paid back."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.orders.models import Order
from plugins.testing import set_app_settings

_PROCESS = 'plugins.installed.orders.refunds.RefundService.process'


def _order(status='pending', payment_status='unpaid'):
    order = Order.objects.create(
        email='c@example.com',
        subtotal=Money(Decimal('20'), 'USD'),
        total=Money(Decimal('20'), 'USD'),
        payment_status=payment_status,
        payment_gateway='stripe',
    )
    if status != 'pending':
        Order.objects.filter(pk=order.pk).update(status=status)
        order = Order.objects.get(pk=order.pk)
    return order


def _status(order):
    return Order.objects.get(pk=order.pk).status


class DashboardCancelTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='cancel-staff', email='staff@example.com', password='x', is_staff=True
        )
        self.client.force_login(staff)

    def _cancel(self, order):
        return self.client.post(
            f'/dashboard/orders/{order.order_number}/action/', {'action': 'cancel'}
        )

    def test_a_shipped_order_is_refused_with_a_reason(self):
        order = _order('shipped', payment_status='paid')
        response = self._cancel(order)
        self.assertEqual(_status(order), 'shipped')
        text = ' '.join(str(m) for m in get_messages(response.wsgi_request))
        self.assertIn('shipped', text)

    def test_a_paid_order_is_paid_back_when_the_setting_says_so(self):
        set_app_settings(self, 'orders', staff_cancel_refund='refund')
        order = _order('confirmed', payment_status='paid')
        with mock.patch(_PROCESS) as process:
            self._cancel(order)
        self.assertEqual(_status(order), 'cancelled')
        process.assert_called_once()

    def test_the_page_offers_cancel_only_while_the_order_can_be_cancelled(self):
        open_order = _order('confirmed')
        response = self.client.get(f'/dashboard/orders/{open_order.order_number}/')
        self.assertContains(response, 'value="cancel"')

        shipped = _order('shipped')
        response = self.client.get(f'/dashboard/orders/{shipped.order_number}/')
        self.assertNotContains(response, 'value="cancel"')

    def test_the_confirmation_says_what_happens_to_the_money(self):
        order = _order('confirmed', payment_status='paid')
        response = self.client.get(f'/dashboard/orders/{order.order_number}/')
        self.assertContains(response, 'The payment is left as it is')

        set_app_settings(self, 'orders', staff_cancel_refund='refund')
        response = self.client.get(f'/dashboard/orders/{order.order_number}/')
        self.assertContains(response, 'pays back $20.00')

    def test_bulk_cancel_skips_shipped_orders_and_says_how_many(self):
        open_order = _order('confirmed')
        shipped = _order('shipped')
        response = self.client.post(
            '/dashboard/orders/bulk/',
            {'action': 'cancel', 'ids': [str(open_order.pk), str(shipped.pk)]},
        )
        self.assertEqual(_status(open_order), 'cancelled')
        self.assertEqual(_status(shipped), 'shipped')
        text = ' '.join(str(m) for m in get_messages(response.wsgi_request))
        self.assertIn('Cancelled 1 order', text)
        self.assertIn('1 could not be cancelled', text)
