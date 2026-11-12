"""A refund can be paid back without the gateway (v0.155.0).

Cash on delivery and bank transfer cannot send money back, so until v0.155.0 a
refund of such an order stayed unprocessed: no refund email, and the gift cards,
points and store credit spent on the order were never returned.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.registry import app_registry


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class OfflineRefundTests(TestCase):
    def setUp(self):
        self.orders = app_registry.get('orders')
        self.addCleanup(self.orders.invalidate_config_cache)
        self.buyer = get_user_model().objects.create_user(
            username='cod', email='cod@example.com', password='x'
        )
        self.refunded = []

        def listen(**kwargs):
            self.refunded.append(kwargs)

        hook_registry.register(MorpheusEvents.PAYMENT_REFUNDED, listen, plugin=None)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.PAYMENT_REFUNDED, listen)

    def _order(self, gateway='cod', customer=True):
        from plugins.installed.orders.models import Order

        return Order.objects.create(
            email='cod@example.com',
            customer=self.buyer if customer else None,
            subtotal=Money(30, 'USD'),
            total=Money(30, 'USD'),
            status='delivered',
            payment_status='paid',
            payment_gateway=gateway,
        )

    def _refund(self, order, amount=10, settle=''):
        from plugins.installed.orders.refunds import RefundService

        return RefundService.process(order=order, amount=Money(amount, 'USD'), settle=settle)

    def test_store_credit_pays_it_back_into_the_account(self):
        from plugins.installed.orders import store_credit

        order = self._order()
        refund = self._refund(order, settle='store_credit')
        self.assertTrue(refund.is_processed)
        self.assertEqual(store_credit.balance(self.buyer).amount, Decimal('10'))
        self.assertEqual(len(self.refunded), 1)
        self.assertEqual(self.refunded[0]['settled_as'], 'store_credit')
        self.assertTrue(order.events.filter(event_type='REFUND_STORE_CREDIT').exists())
        (email,) = mail.outbox
        self.assertIn('store credit', email.body)
        # A retry of the same refund pays nothing twice.
        self._refund(order, settle='store_credit')
        self.assertEqual(store_credit.balance(self.buyer).amount, Decimal('10'))
        self.assertEqual(len(self.refunded), 1)

    def test_external_records_it_as_paid_back(self):
        order = self._order(customer=False)
        refund = self._refund(order, settle='external')
        self.assertTrue(refund.is_processed)
        self.assertTrue(order.events.filter(event_type='REFUND_RECORDED').exists())
        (email,) = mail.outbox
        self.assertIn('paid back to you directly', email.body)

    def test_a_guest_cannot_get_store_credit_and_nonsense_is_refused(self):
        with self.assertRaisesMessage(ValueError, 'guest'):
            self._refund(self._order(customer=False), settle='store_credit')
        with self.assertRaisesMessage(ValueError, 'Unknown way'):
            self._refund(self._order(), settle='cheque')

    def test_the_default_leaves_it_to_settle_by_hand(self):
        from plugins.installed.orders.refunds import default_settle

        order = self._order()
        self.assertEqual(default_settle(order), '')
        refund = self._refund(order)
        self.assertFalse(refund.is_processed)
        self.assertEqual(self.refunded, [])

    def test_the_setting_picks_the_offline_default(self):
        from plugins.installed.orders.refunds import default_settle

        self.orders.set_config('offline_refund_default', 'store_credit')
        self.assertEqual(default_settle(self._order()), 'store_credit')
        self.assertEqual(default_settle(self._order(customer=False)), '')
        self.assertEqual(default_settle(self._order(gateway='stripe')), '')
        self.orders.set_config('offline_refund_default', 'external')
        self.assertEqual(default_settle(self._order(gateway='manual')), 'external')

    def test_the_form_offers_the_choices_and_starts_on_the_default(self):
        from plugins.installed.admin_dashboard.forms.orders import RefundForm

        self.orders.set_config('offline_refund_default', 'store_credit')
        form = RefundForm(order=self._order())
        self.assertEqual(form.fields['settle'].initial, 'store_credit')
        self.assertEqual(
            [v for v, _ in form.fields['settle'].choices], ['', 'store_credit', 'external']
        )
        guest = RefundForm(order=self._order(customer=False))
        self.assertEqual([v for v, _ in guest.fields['settle'].choices], ['', 'external'])
        posted = RefundForm(
            {'amount': '5', 'reason': 'other', 'settle': 'external'}, order=self._order()
        )
        self.assertTrue(posted.is_valid(), posted.errors)
        self.assertTrue(posted.save().is_processed)

    def test_linda_follows_the_default_unless_told(self):
        from plugins.installed.orders.agent_tools import refund_order_tool

        self.orders.set_config('offline_refund_default', 'external')
        order = self._order()
        result = refund_order_tool.invoke(
            {
                'order_number': order.order_number,
                'amount': 5,
                'confirmed': True,
                'hard_gate_ack': 'YES',
                'echo': order.order_number,
            }
        )
        self.assertTrue(result.output['processed'])
        self.assertEqual(self.refunded[0]['settled_as'], 'external')
