"""A guest's orders show up under their account once they prove the email.

Nothing linked a guest order to the account its buyer later created, so
"My orders" never showed purchases made before signing up. Linking happens only
when the person proves control of the address (CUSTOMER_EMAIL_VERIFIED) — email
verification at signup is optional, so linking there would hand anyone who
registers with someone else's email that person's orders and addresses.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.orders.models import Order


def _order(email, customer=None):
    return Order.objects.create(
        email=email,
        customer=customer,
        subtotal=Money(Decimal('8.00'), 'USD'),
        total=Money(Decimal('8.00'), 'USD'),
    )


class GuestOrderLinkingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.ana = User.objects.create_user(username='ana', email='Ana@Example.com', password='x')
        cleo = User.objects.create_user(username='cleo', email='cleo@example.com', password='x')
        self.guest = _order('ana@example.com')
        self.someone_elses = _order('ben@example.com')
        self.on_another_account = _order('ana@example.com', customer=cleo)

    def _owner(self, order):
        return Order.objects.values_list('customer_id', flat=True).get(pk=order.pk)

    def test_a_verified_email_files_its_guest_orders_under_the_account(self):
        hook_registry.fire(
            MorpheusEvents.CUSTOMER_EMAIL_VERIFIED, customer=self.ana, email=self.ana.email
        )
        self.assertEqual(self._owner(self.guest), self.ana.pk)
        self.assertIsNone(self._owner(self.someone_elses))
        self.assertNotEqual(self._owner(self.on_another_account), self.ana.pk)

    def test_registering_alone_links_nothing(self):
        hook_registry.fire(MorpheusEvents.CUSTOMER_REGISTERED, customer=self.ana)
        self.assertIsNone(self._owner(self.guest))
