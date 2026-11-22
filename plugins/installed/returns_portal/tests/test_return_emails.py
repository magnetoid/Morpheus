"""The customer's return emails, and paying a charged exchange (C4, v0.188.0)."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.template.loader import get_template
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from core.hooks import hook_registry
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.orders.models import Fulfillment, FulfillmentItem, Order, OrderItem, Refund
from plugins.installed.orders.refunds import ReturnRequest, ReturnService
from plugins.testing import set_app_settings


def _usd(n):
    return Money(n, 'USD')


class _Base(TestCase):
    def setUp(self):
        self.book = Product.objects.create(
            name='Zephyr Atlas', slug='zephyr-atlas', sku='ZA', price=10, product_type='variable'
        )
        self.paperback = ProductVariant.objects.create(
            product=self.book, name='Paperback', sku='ZA-PB', price=_usd(10)
        )
        self.hardback = ProductVariant.objects.create(
            product=self.book, name='Hardback', sku='ZA-HB', price=_usd(10)
        )
        self.deluxe = ProductVariant.objects.create(
            product=self.book, name='Deluxe', sku='ZA-DX', price=_usd(30)
        )
        customer = get_user_model().objects.create_user(
            username='quillon', email='account@example.com', password='x'
        )
        self.order = Order.objects.create(
            customer=customer,
            email='quillon@example.com',
            subtotal=_usd(10),
            total=_usd(10),
            payment_status='paid',
            payment_gateway='manual',
            shipping_address={'line1': '1 Zephyr Way', 'country': 'US'},
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.book,
            variant=self.paperback,
            product_name='Zephyr Atlas',
            variant_name='Paperback',
            quantity=1,
            unit_price=_usd(10),
            total_price=_usd(10),
        )
        parcel = Fulfillment.objects.create(
            order=self.order,
            shipped_at=timezone.now() - timedelta(days=3),
            delivered_at=timezone.now(),
        )
        FulfillmentItem.objects.create(fulfillment=parcel, order_item=self.item, quantity=1)
        self.items = [{'order_item_id': str(self.item.pk), 'quantity': 1}]

    def request(self):
        with self.captureOnCommitCallbacks(execute=True):
            return ReturnService.create_request(
                order=self.order, items=self.items, reason='changed_mind', window_days=30
            )

    def approved(self):
        rr = ReturnRequest.objects.create(order=self.order, state='requested', items=self.items)
        with self.captureOnCommitCallbacks(execute=True):
            return ReturnService.approve(rr)

    def close_exchange(self, rr, variant, fee=None):
        from plugins.installed.orders.exchange import ExchangeLine

        lines = [ExchangeLine(order_item_id=str(self.item.pk), variant_id=str(variant.pk))]
        with self.captureOnCommitCallbacks(execute=True):
            return ReturnService.close(rr, outcome='exchange', exchange=lines, fee=fee)

    def sent(self, words):
        return [m for m in mail.outbox if words in m.subject]


class ReturnEmailTests(_Base):
    def test_request_sends_return_requested_to_the_order_email(self):
        rr = self.request()
        [message] = self.sent('We received your return request')
        self.assertEqual(message.to, ['quillon@example.com'])
        self.assertIn(rr.rma_number, message.subject)
        body = message.alternatives[0][0] if message.alternatives else message.body
        self.assertIn(f'/account/returns/{rr.pk}/?token={self.order.public_token}', body)

    def test_a_withdrawal_gets_its_own_receipt_not_a_second_one(self):
        with self.captureOnCommitCallbacks(execute=True):
            ReturnService.create_request(order=self.order, items=self.items, reason='withdrawal')
        self.assertEqual(self.sent('We received your return request'), [])

    def test_approval_email_carries_the_instructions(self):
        set_app_settings(
            self, 'returns_portal', return_instructions='Send it to 9 Quillon Lane.\nUse a box.'
        )
        rr = self.approved()
        [message] = self.sent('is approved')
        self.assertIn(rr.rma_number, message.subject)
        self.assertIn('Send it to 9 Quillon Lane.', message.body)
        self.assertIn('<br>Use a box.', message.alternatives[0][0])

    def test_rejection_email_carries_the_staff_note(self):
        rr = ReturnRequest.objects.create(order=self.order, state='requested', items=self.items)
        with self.captureOnCommitCallbacks(execute=True):
            ReturnService.reject(rr, staff_note='The seal on this one was broken.')
        [message] = self.sent('About your return')
        self.assertIn('The seal on this one was broken.', message.body)

    def test_closing_email_names_unmade_lines(self):
        rr = self.approved()
        self.close_exchange(rr, self.deluxe)  # dearer: it cannot be made, so refunded
        [message] = self.sent('is closed')
        self.assertIn('Zephyr Atlas', message.body)
        self.assertIn('could not be exchanged', message.body)
        self.assertIn('Refund', message.body)

    def test_closing_email_names_the_exchange_order(self):
        rr = self.approved()
        self.close_exchange(rr, self.hardback)
        new = Order.objects.get(metadata__exchange_of=rr.rma_number)
        [message] = self.sent('is closed')
        self.assertIn(new.order_number, message.body)
        self.assertEqual(self.sent('Pay for order'), [])

    def test_templates_compile(self):
        for key in ('return_requested', 'return_approved', 'return_rejected', 'return_closed'):
            for ext in ('html', 'txt'):
                with self.subTest(template=f'{key}.{ext}'):
                    get_template(f'emails/{key}.{ext}')

    def test_disabled_app_sends_nothing(self):
        from plugins.registry import app_registry

        app_registry.deactivate('returns_portal')
        self.addCleanup(app_registry.activate, 'returns_portal')
        self.request()
        self.assertEqual(self.sent('We received your return request'), [])


class ChargedExchangeTests(_Base):
    def setUp(self):
        super().setUp()
        self.rr = self.approved()
        self.close_exchange(self.rr, self.hardback, fee=_usd(5))
        self.new = Order.objects.get(metadata__exchange_of=self.rr.rma_number)

    def test_charged_exchange_sends_the_payment_link(self):
        [link] = self.sent('Pay for order')
        self.assertIn(self.new.order_number, link.subject)
        self.assertEqual(link.to, ['quillon@example.com'])
        [closed] = self.sent('is closed')
        self.assertIn('once it is paid', closed.body)

    def test_a_failing_payment_link_never_breaks_the_close(self):
        from unittest import mock

        rr = ReturnRequest.objects.create(order=self.order, state='approved', items=self.items)
        with mock.patch(
            'plugins.installed.payments.pay_link.send', side_effect=RuntimeError('smtp down')
        ):
            self.close_exchange(rr, self.hardback, fee=_usd(5))
        rr.refresh_from_db()
        self.assertEqual(rr.state, 'refunded')

    def test_cancelled_unpaid_exchange_refunds_the_return(self):
        fired = []
        saved = list(hook_registry._handlers.get('return.refunded', []))
        self.addCleanup(hook_registry._handlers.__setitem__, 'return.refunded', saved)
        hook_registry.register('return.refunded', lambda **kw: fired.append(kw), priority=1)
        with self.captureOnCommitCallbacks(execute=True):
            self.new.cancel(reason='Not paid in time')
            self.new.save()
        refund = Refund.objects.get(order=self.order)
        self.assertEqual(refund.amount, _usd(10))
        self.rr.refresh_from_db()
        self.assertEqual(self.rr.state, 'refunded')
        self.assertIn('not paid', self.rr.staff_note)
        self.assertEqual(fired, [])

    def test_a_paid_exchange_cancelled_later_refunds_nothing_here(self):
        Order.objects.filter(pk=self.new.pk).update(payment_status='paid')
        self.new = Order.objects.get(pk=self.new.pk)
        with self.captureOnCommitCallbacks(execute=True):
            self.new.cancel(reason='Changed mind')
            self.new.save()
        self.assertFalse(Refund.objects.filter(order=self.order).exists())
