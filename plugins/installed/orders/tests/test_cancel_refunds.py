"""Cancelling an order, and what happens to its money (v0.180.0).

Until v0.180.0 each door cancelled in its own way: the customer's account
refunded a paid order in full, the dashboard, the bulk action, Linda and
GraphQL cancelled from any status (a delivered order too) and left the money
where it was. Every door now goes through ``orders.cancellation.cancel_with_refund``,
with two settings: whether a staff cancel pays back what was paid
(``staff_cancel_refund``) and whether a customer may cancel a paid order
(``customer_cancel_paid``). An order cannot be cancelled once a parcel of it
is recorded or it has shipped.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django_fsm import TransitionNotAllowed
from djmoney.money import Money

from core.agents.tools import ToolError
from plugins.installed.orders import cancellation
from plugins.installed.orders.models import Fulfillment, Order, Refund
from plugins.installed.orders.refunds import RefundService
from plugins.testing import set_app_settings

_PROCESS = 'plugins.installed.orders.refunds.RefundService.process'


def _usd(n):
    return Money(Decimal(str(n)), 'USD')


def _order(status='pending', payment_status='unpaid', gateway='stripe', customer=None):
    order = Order.objects.create(
        email='c@example.com',
        customer=customer,
        subtotal=_usd(20),
        total=_usd(20),
        payment_status=payment_status,
        payment_gateway=gateway,
    )
    if status != 'pending':
        Order.objects.filter(pk=order.pk).update(status=status)
        order = Order.objects.get(pk=order.pk)
    return order


def _status(order):
    return Order.objects.get(pk=order.pk).status


class CancelTransitionTests(TestCase):
    def test_an_order_that_has_not_shipped_can_be_cancelled(self):
        for status in ('pending', 'confirmed', 'processing', 'fulfilled'):
            with self.subTest(status=status):
                order = _order(status)
                order.cancel()
                self.assertEqual(order.status, 'cancelled')

    def test_a_shipped_or_closed_order_cannot_be_cancelled(self):
        # partially_fulfilled: a parcel has left by definition.
        for status in ('partially_fulfilled', 'shipped', 'delivered', 'refunded', 'cancelled'):
            with self.subTest(status=status):
                order = _order(status)
                with self.assertRaises(TransitionNotAllowed):
                    order.cancel()

    def test_a_cancelled_or_refunded_order_is_not_marked_refunded(self):
        for status in ('cancelled', 'refunded'):
            with self.subTest(status=status), self.assertRaises(TransitionNotAllowed):
                _order(status).mark_refunded()

    def test_a_delivered_order_can_still_be_marked_refunded(self):
        order = _order('delivered')
        order.mark_refunded()
        self.assertEqual(order.status, 'refunded')

    def test_a_refund_recorded_for_a_cancelled_order_keeps_it_cancelled(self):
        # Before the FSM was narrowed this moved a cancelled order to refunded;
        # now the transition would refuse and roll the recorded refund back.
        order = _order('cancelled', payment_status='paid')
        refund = RefundService.record_external(order=order, notes='Paid back in cash')
        self.assertTrue(refund.is_processed)
        self.assertEqual(_status(order), 'cancelled')


class StaffCancelTests(TestCase):
    def test_the_payment_is_left_as_it_is_by_default(self):
        order = _order('confirmed', payment_status='paid')
        with mock.patch(_PROCESS) as process:
            result = cancellation.cancel_with_refund(order, reason='Out of stock')
        process.assert_not_called()
        self.assertEqual(result.order.status, 'cancelled')
        self.assertEqual(_status(order), 'cancelled')
        self.assertIsNone(result.refund)
        self.assertIn('Issue refund', result.note)

    def test_the_setting_pays_back_what_is_left(self):
        set_app_settings(self, 'orders', staff_cancel_refund='refund')
        order = _order('processing', payment_status='paid')
        Refund.objects.create(order=order, amount=_usd(5), is_processed=True)
        with mock.patch(_PROCESS) as process:
            cancellation.cancel_with_refund(order, reason='Out of stock')
        process.assert_called_once()
        kwargs = process.call_args.kwargs
        self.assertEqual(kwargs['order'].pk, order.pk)
        self.assertEqual(kwargs['amount'], _usd(15))
        self.assertEqual(kwargs['settle'], '')

    def test_a_refund_still_waiting_to_be_paid_back_is_not_paid_twice(self):
        set_app_settings(self, 'orders', staff_cancel_refund='refund')
        order = _order('processing', payment_status='paid')
        Refund.objects.create(order=order, amount=_usd(5), is_processed=False)
        with mock.patch(_PROCESS) as process:
            cancellation.cancel_with_refund(order)
        self.assertEqual(process.call_args.kwargs['amount'], _usd(15))

    def test_an_order_paid_offline_follows_the_offline_refund_setting(self):
        set_app_settings(
            self, 'orders', staff_cancel_refund='refund', offline_refund_default='external'
        )
        order = _order('confirmed', payment_status='paid', gateway='cod')
        result = cancellation.cancel_with_refund(order)
        self.assertEqual(result.refund.amount, _usd(20))
        self.assertTrue(result.refund.is_processed)
        self.assertEqual(_status(order), 'cancelled')
        self.assertIn('paid back', result.note)

    def test_a_refund_the_gateway_has_not_paid_back_says_so(self):
        # A card order with no recorded charge: the refund row stays unprocessed.
        set_app_settings(self, 'orders', staff_cancel_refund='refund')
        order = _order('confirmed', payment_status='paid')
        result = cancellation.cancel_with_refund(order)
        self.assertFalse(result.refund.is_processed)
        self.assertEqual(result.refund_state, 'waiting')
        self.assertIn('not been paid back', result.note)

    def test_an_order_with_a_parcel_on_its_way_cannot_be_cancelled(self):
        # With fulfil_marks_shipped off, an order whose parcels have left stays
        # 'fulfilled'; cancelling it would re-credit gift cards and points in full.
        set_app_settings(self, 'orders', staff_cancel_refund='refund')
        order = _order('fulfilled', payment_status='paid')
        Fulfillment.objects.create(order=order, tracking_number='T1')
        self.assertFalse(cancellation.preview(order)['allowed'])
        with mock.patch(_PROCESS) as process, self.assertRaises(cancellation.CancelRefused) as e:
            cancellation.cancel_with_refund(order)
        process.assert_not_called()
        self.assertEqual(_status(order), 'fulfilled')
        self.assertIn('parcel on its way', str(e.exception))

    def test_a_packed_order_with_no_parcel_can_still_be_cancelled(self):
        order = _order('fulfilled')
        self.assertTrue(cancellation.preview(order)['allowed'])
        cancellation.cancel_with_refund(order)
        self.assertEqual(_status(order), 'cancelled')

    def test_a_held_card_payment_is_released_not_refunded(self):
        set_app_settings(self, 'orders', staff_cancel_refund='refund')
        order = _order('confirmed', payment_status='authorized')
        with mock.patch(_PROCESS) as process:
            result = cancellation.cancel_with_refund(order)
        process.assert_not_called()
        self.assertIn('released', result.note)

    def test_an_unpaid_order_has_nothing_to_pay_back(self):
        set_app_settings(self, 'orders', staff_cancel_refund='refund')
        with mock.patch(_PROCESS) as process:
            cancellation.cancel_with_refund(_order('pending'))
        process.assert_not_called()

    def test_a_failed_refund_leaves_the_order_cancelled(self):
        set_app_settings(self, 'orders', staff_cancel_refund='refund')
        order = _order('confirmed', payment_status='paid')
        with mock.patch(_PROCESS, side_effect=RuntimeError('gateway down')):
            result = cancellation.cancel_with_refund(order)
        self.assertEqual(_status(order), 'cancelled')
        self.assertIsNone(result.refund)
        self.assertEqual(result.refund_state, 'failed')
        self.assertIn('failed', result.note)

    def test_a_shipped_order_is_refused_and_left_alone(self):
        for status in ('shipped', 'delivered', 'cancelled', 'refunded'):
            with self.subTest(status=status):
                order = _order(status, payment_status='paid')
                with self.assertRaises(cancellation.CancelRefused):
                    cancellation.cancel_with_refund(order)
                self.assertEqual(_status(order), status)

    def test_the_order_is_read_again_before_it_is_cancelled(self):
        # The caller's copy says pending; the order shipped meanwhile.
        order = _order('pending')
        Order.objects.filter(pk=order.pk).update(status='shipped')
        with self.assertRaises(cancellation.CancelRefused):
            cancellation.cancel_with_refund(order)
        self.assertEqual(_status(order), 'shipped')


class CustomerCancelTests(TestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user(
            username='cc-buyer', email='cc@example.com', password='x'
        )

    def test_a_customer_may_cancel_only_before_the_order_is_packed(self):
        for status, expected in (
            ('pending', True),
            ('confirmed', True),
            ('processing', True),
            ('partially_fulfilled', False),
            ('fulfilled', False),
            ('shipped', False),
        ):
            with self.subTest(status=status):
                order = _order(status, customer=self.buyer)
                self.assertIs(cancellation.customer_can_cancel(order), expected)

    def test_a_paid_order_is_paid_back_in_full_by_default(self):
        order = _order('confirmed', payment_status='paid', customer=self.buyer)
        with mock.patch(_PROCESS) as process:
            cancellation.cancel_with_refund(order, actor=self.buyer, by_customer=True)
        kwargs = process.call_args.kwargs
        self.assertEqual(kwargs['amount'], _usd(20))
        self.assertEqual(kwargs['reason'], 'customer_request')

    def test_contact_keeps_paid_orders_for_the_store(self):
        set_app_settings(self, 'orders', customer_cancel_paid='contact')
        paid = _order('confirmed', payment_status='paid', customer=self.buyer)
        self.assertFalse(cancellation.customer_can_cancel(paid))
        with self.assertRaises(cancellation.CancelRefused):
            cancellation.cancel_with_refund(paid, actor=self.buyer, by_customer=True)
        self.assertEqual(_status(paid), 'confirmed')

        unpaid = _order('pending', customer=self.buyer)
        self.assertTrue(cancellation.customer_can_cancel(unpaid))
        cancellation.cancel_with_refund(unpaid, actor=self.buyer, by_customer=True)
        self.assertEqual(_status(unpaid), 'cancelled')

    def test_the_staff_setting_does_not_change_the_customer_door(self):
        set_app_settings(self, 'orders', staff_cancel_refund='keep')
        order = _order('confirmed', payment_status='paid', customer=self.buyer)
        with mock.patch(_PROCESS) as process:
            cancellation.cancel_with_refund(order, actor=self.buyer, by_customer=True)
        process.assert_called_once()

    def test_a_customer_cancel_never_settles_outside_the_payment_method(self):
        # 'external' would record money as sent that nobody sent, and store
        # credit breaks the account page's promise of the original method.
        for default in ('external', 'store_credit'):
            with self.subTest(default=default):
                set_app_settings(self, 'orders', offline_refund_default=default)
                order = _order(
                    'confirmed', payment_status='paid', gateway='manual', customer=self.buyer
                )
                with mock.patch(_PROCESS) as process:
                    cancellation.cancel_with_refund(order, actor=self.buyer, by_customer=True)
                self.assertEqual(process.call_args.kwargs['settle'], '')


class LindaCancelToolTests(TestCase):
    def _cancel(self, order, **extra):
        from plugins.installed.orders.agent_tools import orders_cancel_tool

        return orders_cancel_tool.invoke(
            {'order_number': order.order_number, 'confirmed': True, **extra}
        )

    def test_a_shipped_order_is_refused(self):
        order = _order('shipped', payment_status='paid')
        with self.assertRaises(ToolError):
            self._cancel(order)
        self.assertEqual(_status(order), 'shipped')

    def test_the_tool_cancels_through_the_same_rules(self):
        set_app_settings(
            self, 'orders', staff_cancel_refund='refund', offline_refund_default='external'
        )
        order = _order('confirmed', payment_status='paid', gateway='cod')
        result = self._cancel(order, reason='customer asked')
        self.assertEqual(_status(order), 'cancelled')
        self.assertEqual(result.output['refund']['amount'], '20.00')
        self.assertTrue(result.output['refund']['paid_back'])

    def test_a_refund_over_the_agent_cap_is_refused_before_cancelling(self):
        set_app_settings(self, 'orders', staff_cancel_refund='refund')
        order = _order('confirmed', payment_status='paid')
        with (
            mock.patch('plugins.installed.orders.agent_tools.max_refund_value', return_value=10),
            mock.patch(_PROCESS) as process,
        ):
            with self.assertRaises(ToolError) as e:
                self._cancel(order)
            self.assertIn('per-refund cap', str(e.exception))
            from plugins.installed.orders.agent_tools import orders_update_status_tool

            with self.assertRaises(ToolError):
                orders_update_status_tool.invoke(
                    {'order_number': order.order_number, 'status': 'cancelled', 'confirmed': True}
                )
        process.assert_not_called()
        self.assertEqual(_status(order), 'confirmed')

    def test_a_cancel_that_pays_nothing_back_ignores_the_cap(self):
        order = _order('confirmed', payment_status='paid')  # setting 'keep'
        with mock.patch('plugins.installed.orders.agent_tools.max_refund_value', return_value=10):
            result = self._cancel(order)
        self.assertEqual(_status(order), 'cancelled')
        self.assertEqual(result.output['refund_state'], 'none')

    def test_a_staged_cancel_says_what_happens_to_the_money(self):
        from core.assistant.models import OpsProposal
        from plugins.installed.orders.agent_tools import orders_cancel_tool

        set_app_settings(self, 'orders', staff_cancel_refund='refund')
        order = _order('confirmed', payment_status='paid')
        orders_cancel_tool.invoke(
            {'order_number': order.order_number},
            context={'staged': True},
        )
        self.assertEqual(_status(order), 'confirmed')
        self.assertIn('pay back', OpsProposal.objects.get().summary)


class GraphQLCancelTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='gql-staff', email='gql@example.test', password='x', is_staff=True
        )
        self.client.force_login(staff)

    def _cancel(self, order):
        query = (
            f'mutation {{ cancelOrder(input: {{orderNumber: "{order.order_number}", '
            'reason: "test"}) { status error } }'
        )
        response = self.client.post(
            '/graphql/', json.dumps({'query': query}), content_type='application/json'
        )
        return response.json()['data']['cancelOrder']

    def test_a_shipped_order_is_refused(self):
        order = _order('shipped')
        data = self._cancel(order)
        self.assertTrue(data['error'])
        self.assertEqual(_status(order), 'shipped')

    def test_an_open_order_is_cancelled(self):
        data = self._cancel(_order('confirmed'))
        self.assertEqual(data['status'], 'cancelled')
        self.assertFalse(data['error'])
