"""Cart-recovery one-click unsubscribe + RFC 8058 headers (deep-debug #11).

The recovery drip is consent-gated marketing email but shipped no
``List-Unsubscribe`` header/footer, so Gmail/Yahoo junked it and a shopper had
no way to opt out. These cover the signed token, the suppression list, the
one-click endpoint, and that the drip now carries the header + skips an opted-
out address.
"""

from __future__ import annotations

from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.cart_abandonment.models import RecoverySuppression
from plugins.installed.cart_abandonment.services import (
    email_from_token,
    is_suppressed,
    suppress_from_token,
    unsubscribe_headers,
    unsubscribe_token,
)
from plugins.installed.catalog.models import Product
from plugins.installed.consent.models import ConsentLog
from plugins.installed.orders.models import Cart, CartItem


class RecoveryTokenTests(TestCase):
    def test_token_round_trips_and_normalises_case(self):
        token = unsubscribe_token('Reader@Example.com')
        self.assertEqual(email_from_token(token), 'reader@example.com')

    def test_forged_token_returns_none(self):
        self.assertIsNone(email_from_token('not-a-real-token'))

    def test_headers_are_the_rfc8058_pair(self):
        h = unsubscribe_headers('r@e.com')
        self.assertTrue(h['List-Unsubscribe'].startswith('<'))
        self.assertTrue(h['List-Unsubscribe'].endswith('>'))
        self.assertEqual(h['List-Unsubscribe-Post'], 'List-Unsubscribe=One-Click')

    def test_suppress_from_token_is_idempotent(self):
        token = unsubscribe_token('r@e.com')
        self.assertFalse(is_suppressed('r@e.com'))
        self.assertEqual(suppress_from_token(token), 'r@e.com')
        self.assertTrue(is_suppressed('r@e.com'))
        self.assertEqual(suppress_from_token(token), 'r@e.com')  # second click
        self.assertEqual(RecoverySuppression.objects.filter(email='r@e.com').count(), 1)


class RecoveryUnsubscribeViewTests(TestCase):
    def test_one_click_post_unsubscribes_without_csrf(self):
        token = unsubscribe_token('click@e.com')
        resp = self.client.post(f'/cart-recovery/unsubscribe/{token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(is_suppressed('click@e.com'))

    def test_footer_link_get_unsubscribes(self):
        token = unsubscribe_token('link@e.com')
        resp = self.client.get(f'/cart-recovery/unsubscribe/{token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(is_suppressed('link@e.com'))

    def test_forged_token_is_404(self):
        resp = self.client.get('/cart-recovery/unsubscribe/garbage/')
        self.assertEqual(resp.status_code, 404)


@override_settings(DEFAULT_FROM_EMAIL='store@example.test')
class RecoveryDripUnsubscribeTests(TestCase):
    def setUp(self) -> None:
        self.product = Product.objects.create(
            name='Unsub Book', slug='unsub-book', sku='UB1', price=Money(18, 'USD'), status='active'
        )

    def _guest_cart(self, *, email='shopper@example.test', age_minutes=90, session='sess-u'):
        cart = Cart.objects.create(session_key=session, metadata={'checkout_email': email})
        CartItem.objects.create(
            cart=cart, product=self.product, quantity=1, unit_price=Money(18, 'USD')
        )
        old = timezone.now() - timedelta(minutes=age_minutes)
        Cart.objects.filter(pk=cart.pk).update(updated_at=old)
        cart.refresh_from_db()
        return cart

    def _consent(self, session='sess-u', marketing=True):
        ConsentLog.objects.create(session_key=session, marketing=marketing)

    def test_drip_carries_list_unsubscribe_header_and_footer(self):
        from plugins.installed.cart_abandonment.tasks import send_cart_recovery_drip

        self._guest_cart()
        self._consent(marketing=True)
        out = send_cart_recovery_drip()
        self.assertEqual(out['sent'], 1)
        msg = mail.outbox[-1]
        self.assertIn('List-Unsubscribe', msg.extra_headers)
        self.assertEqual(msg.extra_headers['List-Unsubscribe-Post'], 'List-Unsubscribe=One-Click')
        self.assertIn('Unsubscribe', msg.body)  # visible footer in the text part

    def test_suppressed_address_is_never_dripped(self):
        from plugins.installed.cart_abandonment.tasks import send_cart_recovery_drip

        self._guest_cart(email='gone@example.test')
        self._consent(marketing=True)
        suppress_from_token(unsubscribe_token('gone@example.test'))
        before = len(mail.outbox)
        out = send_cart_recovery_drip()
        self.assertEqual(out['sent'], 0)
        self.assertEqual(len(mail.outbox), before)
