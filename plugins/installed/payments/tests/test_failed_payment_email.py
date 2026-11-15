"""A declined card can email the customer a link to try again (A8, v0.171.0).

Off by default (``failed_payment_email_minutes`` 0), so no store sends anything
new on deploy. When on, it goes once per order, after the delay, and only while
the order is still unpaid.
"""

from __future__ import annotations

from django.core import mail
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.orders.models import Order
from plugins.installed.payments.models import PaymentTransaction
from plugins.installed.payments.services.stripe import PaymentService
from plugins.installed.payments.tasks import FAILED_EMAIL_KEY, send_failed_payment_email
from plugins.testing import set_app_settings


@override_settings(DEFAULT_FROM_EMAIL='shop@example.com')
class FailedPaymentEmailTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            email='decline@example.com', subtotal=Money(9, 'USD'), total=Money(9, 'USD')
        )
        for n in (1, 2):
            PaymentTransaction.objects.create(
                order=self.order,
                amount=self.order.total,
                provider='stripe',
                provider_transaction_id=f'pi_declined_{n}',
            )

    def decline(self, intent='pi_declined_1'):
        with self.captureOnCommitCallbacks(execute=True):
            PaymentService._mark_transaction_failed(intent, 'Your card was declined.')

    def test_off_by_default(self):
        self.decline()
        self.assertEqual(mail.outbox, [])

    def test_sent_once_with_the_link(self):
        set_app_settings(self, 'payments', failed_payment_email_minutes=10)
        self.decline('pi_declined_1')
        self.decline('pi_declined_2')
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['decline@example.com'])
        self.assertIn("didn't go through", message.subject)
        self.assertIn(f'/pay/{self.order.public_token}/', message.body)
        md = Order.objects.values_list('metadata', flat=True).get(pk=self.order.pk)
        self.assertTrue(md.get(FAILED_EMAIL_KEY))

    def test_not_sent_once_the_order_is_paid(self):
        Order.objects.filter(pk=self.order.pk).update(payment_status='paid')
        self.assertFalse(send_failed_payment_email(str(self.order.pk)))
        self.assertEqual(mail.outbox, [])

    def test_not_sent_for_a_cancelled_order(self):
        Order.objects.filter(pk=self.order.pk).update(status='cancelled')
        self.assertFalse(send_failed_payment_email(str(self.order.pk)))
        self.assertEqual(mail.outbox, [])
