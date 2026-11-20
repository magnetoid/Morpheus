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

    def test_bulk_cancel_skips_shipped_orders_and_names_them(self):
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
        self.assertIn(
            f'Not cancelled (shipped, a parcel on its way, or closed): #{shipped.order_number}',
            text,
        )

    def test_bulk_cancel_names_each_refund_outcome(self):
        set_app_settings(self, 'orders', staff_cancel_refund='refund')
        paid_back = _order('confirmed', payment_status='paid')
        waiting = _order('confirmed', payment_status='paid')
        failed = _order('confirmed', payment_status='paid')

        def process(*, order, amount, **kwargs):
            if order.pk == failed.pk:
                raise RuntimeError('gateway down')
            return mock.Mock(amount=amount, is_processed=order.pk == paid_back.pk)

        with mock.patch(_PROCESS, side_effect=process):
            response = self.client.post(
                '/dashboard/orders/bulk/',
                {'action': 'cancel', 'ids': [str(o.pk) for o in (paid_back, waiting, failed)]},
            )
        text = ' '.join(str(m) for m in get_messages(response.wsgi_request))
        self.assertIn('Cancelled 3 order', text)
        self.assertIn(f'Paid back: #{paid_back.order_number}.', text)
        self.assertIn(
            f'not paid back yet (settle it on the order page): #{waiting.order_number}', text
        )
        self.assertIn(f'Refund failed (refund it from Issue refund): #{failed.order_number}', text)

    def test_a_row_offers_cancel_only_while_the_order_can_be_cancelled(self):
        from plugins.installed.admin_dashboard.templatetags.morph_dashboard import (
            order_row_actions,
        )

        def labels(order):
            return [a['label'] for a in order_row_actions({}, order)['actions']]

        self.assertIn('Cancel', labels(_order('confirmed')))
        for status in ('partially_fulfilled', 'shipped', 'delivered', 'cancelled'):
            with self.subTest(status=status):
                self.assertNotIn('Cancel', labels(_order(status)))
