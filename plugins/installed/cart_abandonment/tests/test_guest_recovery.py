"""Guest-cart recovery (Wave 1 of docs/plans/cutting-edge-open-core-2026-07.md).

Guest carts — the majority of abandonment — were unreachable: the scanner
only read customer.email and the drip queryset excluded customer-less carts.
Checkout now stamps the typed email onto cart.metadata['checkout_email'];
the scanner + drip read it, and consent is resolved by the cart's
session_key for guests. No consent → no send, exactly as for customers.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.consent.models import ConsentLog
from plugins.installed.orders.models import Cart, CartItem


@override_settings(DEFAULT_FROM_EMAIL='store@example.test')
class GuestRecoveryTests(TestCase):
    def setUp(self) -> None:
        self.product = Product.objects.create(
            name='Guest Book',
            slug='guest-book',
            sku='GB1',
            price=Money(18, 'USD'),
            status='active',
        )

    def _guest_cart(self, *, email='guest@example.test', age_minutes=90, session='sess-1'):
        metadata = {'checkout_email': email} if email else {}
        cart = Cart.objects.create(session_key=session, metadata=metadata)
        CartItem.objects.create(
            cart=cart, product=self.product, quantity=1, unit_price=Money(18, 'USD')
        )
        old = timezone.now() - timedelta(minutes=age_minutes)
        Cart.objects.filter(pk=cart.pk).update(updated_at=old)
        cart.refresh_from_db()
        return cart

    def _consent(self, session='sess-1', marketing=True):
        ConsentLog.objects.create(session_key=session, marketing=marketing)

    def test_scanner_fires_for_guest_with_stamped_email(self):
        from plugins.installed.cart_abandonment.tasks import scan_abandoned_carts

        self._guest_cart()
        with patch('core.hooks.hook_registry.fire') as fire:
            out = scan_abandoned_carts()
        self.assertEqual(out['fired'], 1)
        self.assertEqual(fire.call_args.kwargs['email'], 'guest@example.test')

    def test_scanner_still_skips_guest_without_email(self):
        from plugins.installed.cart_abandonment.tasks import scan_abandoned_carts

        self._guest_cart(email='')
        out = scan_abandoned_carts()
        self.assertEqual(out['fired'], 0)

    def test_drip_reaches_consented_guest(self):
        from django.core import mail

        from plugins.installed.cart_abandonment.tasks import send_cart_recovery_drip

        self._guest_cart()
        self._consent(marketing=True)
        out = send_cart_recovery_drip()
        self.assertEqual(out['sent'], 1)  # step 1 due at 60m; cart is 90m old
        self.assertEqual(mail.outbox[-1].to, ['guest@example.test'])

    def test_drip_never_emails_guest_without_consent(self):
        from django.core import mail

        from plugins.installed.cart_abandonment.tasks import send_cart_recovery_drip

        self._guest_cart()  # no ConsentLog at all
        before = len(mail.outbox)
        out = send_cart_recovery_drip()
        self.assertEqual(out['sent'], 0)
        self.assertEqual(len(mail.outbox), before)

    def test_drip_respects_guest_opt_out(self):
        from plugins.installed.cart_abandonment.tasks import send_cart_recovery_drip

        self._guest_cart()
        self._consent(marketing=False)
        self.assertEqual(send_cart_recovery_drip()['sent'], 0)
