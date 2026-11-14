"""The newsletter tick at checkout (newsletter/checkout.py).

Off by default. When on, the checkout asks "Email me news and offers", never ticked
in advance and never required; an order whose shopper ticked it starts the same double
opt-in as the signup forms, once the order commits.
"""

from __future__ import annotations

from decimal import Decimal

from django.core import mail
from django.test import TestCase
from djmoney.money import Money

from core import checkout_fields
from plugins.installed.customers.models import Customer
from plugins.installed.newsletter.checkout import on_order_placed
from plugins.installed.newsletter.models import NewsletterSubscriber
from plugins.installed.orders.models import Order
from plugins.testing import set_app_settings


def _order(answers=None, customer=None):
    return Order.objects.create(
        email='Buyer@Example.com',
        customer=customer,
        subtotal=Money(Decimal('8.00'), 'USD'),
        total=Money(Decimal('8.00'), 'USD'),
        metadata={'checkout_fields': answers} if answers else {},
    )


class OptInFieldTests(TestCase):
    def keys(self, user=None):
        return [f['key'] for f in checkout_fields.fields(user=user)]

    def test_off_by_default(self):
        self.assertNotIn('newsletter_opt_in', self.keys())

    def test_on_it_is_an_optional_unticked_box(self):
        set_app_settings(self, 'newsletter', checkout_opt_in=True)
        field = next(f for f in checkout_fields.fields() if f['key'] == 'newsletter_opt_in')
        self.assertEqual(field['kind'], 'checkbox')
        self.assertFalse(field['required'])
        self.assertFalse(checkout_fields.has_required())

    def test_a_confirmed_subscriber_is_not_asked_again(self):
        set_app_settings(self, 'newsletter', checkout_opt_in=True)
        shopper = Customer.objects.create_user(
            email='ana@example.com', username='ana', password='x'
        )
        self.assertIn('newsletter_opt_in', self.keys(user=shopper))
        NewsletterSubscriber.objects.create(email='ana@example.com', status='confirmed')
        self.assertNotIn('newsletter_opt_in', self.keys(user=shopper))


class OptInOrderTests(TestCase):
    def test_a_ticked_order_starts_the_double_opt_in_after_commit(self):
        order = _order({'newsletter_opt_in': True})
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            on_order_placed(order=order)
        self.assertFalse(NewsletterSubscriber.objects.exists())
        for callback in callbacks:
            callback()
        sub = NewsletterSubscriber.objects.get()
        self.assertEqual(sub.email, 'buyer@example.com')
        self.assertEqual(sub.status, 'pending')
        self.assertEqual(sub.source, 'checkout')
        self.assertEqual(len(mail.outbox), 1)

    def test_an_unticked_order_subscribes_nobody(self):
        with self.captureOnCommitCallbacks(execute=True):
            on_order_placed(order=_order({'order_notes': 'Ring twice'}))
            on_order_placed(order=_order())
        self.assertFalse(NewsletterSubscriber.objects.exists())
