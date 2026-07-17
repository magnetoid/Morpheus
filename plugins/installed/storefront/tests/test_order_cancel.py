"""Customer pre-dispatch order cancellation (EU right of withdrawal).

Guards: only the owner, only before dispatch, and a paid order is refunded
through the idempotent RefundService (never a raw Stripe call here).
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.orders.models import Order

_REFUND = 'plugins.installed.orders.refunds.RefundService.process'


def _status(order):
    # django-fsm blocks refresh_from_db() on the protected status field, so read
    # it back with a fresh fetch (the idiom used across the orders tests).
    return Order.objects.get(pk=order.pk).status


def _make_order(customer, *, status='pending', payment_status='unpaid'):
    order = Order.objects.create(
        customer=customer,
        email=customer.email or 'buyer@example.com',
        subtotal=Money(20, 'USD'),
        total=Money(20, 'USD'),
        payment_status=payment_status,
    )
    if status != 'pending':
        # status is a protected FSMField — set the fixture state directly in the
        # DB and re-fetch, rather than walking the whole transition chain.
        Order.objects.filter(pk=order.pk).update(status=status)
        order = Order.objects.get(pk=order.pk)
    return order


class OrderCancelTests(TestCase):
    def setUp(self):
        self.client = Client()
        User = get_user_model()
        self.buyer = User.objects.create_user(
            username='buyer', email='buyer@example.com', password='pw-12345'
        )
        self.other = User.objects.create_user(
            username='other', email='other@example.com', password='pw-12345'
        )

    def _url(self, order):
        return f'/account/orders/{order.order_number}/cancel/'

    def test_anon_is_redirected_to_login(self):
        order = _make_order(self.buyer)
        resp = self.client.post(self._url(order))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/auth/login/', resp['Location'])

    def test_owner_can_cancel_pending_order(self):
        order = _make_order(self.buyer, status='pending')
        self.client.force_login(self.buyer)
        resp = self.client.post(self._url(order))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(_status(order), 'cancelled')

    def test_cancel_refused_after_dispatch(self):
        order = _make_order(self.buyer, status='shipped')
        self.client.force_login(self.buyer)
        resp = self.client.post(self._url(order))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(_status(order), 'shipped')  # untouched

    def test_get_does_not_cancel(self):
        order = _make_order(self.buyer, status='pending')
        self.client.force_login(self.buyer)
        self.client.get(self._url(order))
        self.assertEqual(_status(order), 'pending')

    def test_cannot_cancel_another_users_order(self):
        order = _make_order(self.other, status='pending')
        self.client.force_login(self.buyer)
        resp = self.client.post(self._url(order))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(_status(order), 'pending')

    def test_paid_order_is_refunded_in_full(self):
        order = _make_order(self.buyer, status='confirmed', payment_status='paid')
        self.client.force_login(self.buyer)
        with patch(_REFUND) as mock_process:
            self.client.post(self._url(order))
        self.assertEqual(_status(order), 'cancelled')
        mock_process.assert_called_once()
        kwargs = mock_process.call_args.kwargs
        self.assertEqual(kwargs['order'].pk, order.pk)
        self.assertEqual(kwargs['amount'], order.total)

    def test_unpaid_order_does_not_call_refund(self):
        order = _make_order(self.buyer, status='pending', payment_status='unpaid')
        self.client.force_login(self.buyer)
        with patch(_REFUND) as mock_process:
            self.client.post(self._url(order))
        mock_process.assert_not_called()

    def test_refund_failure_still_cancels_the_order(self):
        order = _make_order(self.buyer, status='pending', payment_status='paid')
        self.client.force_login(self.buyer)
        with patch(_REFUND, side_effect=RuntimeError('gateway down')):
            resp = self.client.post(self._url(order))
        self.assertEqual(resp.status_code, 302)  # did not 500
        self.assertEqual(_status(order), 'cancelled')

    def test_cancel_button_shown_only_when_cancellable(self):
        self.client.force_login(self.buyer)
        pending = _make_order(self.buyer, status='pending')
        resp = self.client.get(f'/account/orders/{pending.order_number}/')
        self.assertContains(resp, 'Cancel this order')

        shipped = _make_order(self.buyer, status='shipped')
        resp = self.client.get(f'/account/orders/{shipped.order_number}/')
        self.assertNotContains(resp, 'Cancel this order')
