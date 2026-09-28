"""An order-placed email actually goes out.

``test_checkout.CheckoutFlowTests.test_order_confirmation_email_is_sent`` is
skipped on SQLite, which is where every local run happens, and the email
templates it needed could not be found in production at all. This version
needs no product or variant, so it runs everywhere.
"""

from __future__ import annotations

from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.orders.models import Order


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class OrderPlacedEmailTests(TestCase):
    def test_an_order_placed_email_is_sent(self):
        from core.emails.handlers import on_order_placed

        order = Order.objects.create(
            email='buyer@example.com',
            subtotal=Money(Decimal('8.00'), 'USD'),
            total=Money(Decimal('8.00'), 'USD'),
        )
        with self.captureOnCommitCallbacks(execute=True):
            on_order_placed(order)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(order.order_number, mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ['buyer@example.com'])
