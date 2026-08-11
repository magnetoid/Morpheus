"""Cart-recovery drip: the single, consent-checked recovery-email path.

Covers step timing, idempotency, marketing-consent gating, the
recovered-cart guard, and that the two retired senders (core/emails +
marketing) no longer register a CART_ABANDONED email handler.
"""

from __future__ import annotations

from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.consent.models import ConsentLog
from plugins.installed.customers.models import Customer
from plugins.installed.orders.models import Cart, CartItem


@override_settings(DEFAULT_FROM_EMAIL='store@example.test')
class CartRecoveryDripTests(TestCase):
    def setUp(self) -> None:
        self.product = Product.objects.create(
            name='Test Book',
            slug='test-book-drip',
            sku='TBD',
            price=Money(20, 'USD'),
            status='active',
        )
        self.customer = Customer.objects.create_user(
            email='buyer@example.test', username='buyer', password='x'
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _cart(self, *, customer=None, with_item=True, age_minutes=None, metadata=None) -> Cart:
        cart = Cart.objects.create(
            customer=customer if customer is not None else self.customer,
            metadata=metadata or {},
        )
        if with_item:
            CartItem.objects.create(
                cart=cart, product=self.product, quantity=1, unit_price=Money(20, 'USD')
            )
        if age_minutes is not None:
            # updated_at is auto_now; bypass it with a direct UPDATE so the
            # cart reads as abandoned.
            old = timezone.now() - timedelta(minutes=age_minutes)
            Cart.objects.filter(pk=cart.pk).update(updated_at=old)
            cart.refresh_from_db()
        return cart

    def _consent(self, marketing: bool) -> None:
        ConsentLog.objects.create(customer=self.customer, session_key='s', marketing=marketing)

    def _run(self):
        from plugins.installed.cart_abandonment.tasks import send_cart_recovery_drip

        return send_cart_recovery_drip()

    def _scan(self):
        from plugins.installed.cart_abandonment.tasks import scan_abandoned_carts

        return scan_abandoned_carts()

    def _set_abandoned_emitted(self, cart, *, minutes_ago: int) -> None:
        """Backdate the cart's 'abandoned_emitted' anchor without touching
        updated_at (which auto_now would otherwise bump)."""
        meta = dict(cart.metadata or {})
        meta['abandoned_emitted'] = (timezone.now() - timedelta(minutes=minutes_ago)).isoformat()
        Cart.objects.filter(pk=cart.pk).update(metadata=meta)
        cart.refresh_from_db()

    # ── (a) step 1 timing ─────────────────────────────────────────────────────

    def test_step1_does_not_send_before_delay(self):
        self._consent(marketing=True)
        self._cart(age_minutes=30)  # < 60
        self._run()
        self.assertEqual(len(mail.outbox), 0)

    def test_step1_sends_once_when_due(self):
        self._consent(marketing=True)
        self._cart(age_minutes=90)  # >= 60, < 1440
        self._run()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['buyer@example.test'])
        self.assertEqual(mail.outbox[0].subject, 'You left items in your cart')

    # ── (b) step 2 timing ─────────────────────────────────────────────────────

    def test_step2_only_after_delay2(self):
        self._consent(marketing=True)
        # Age past step 2 (1440) but not step 3 (4320): both step 1 and 2 due.
        cart = self._cart(age_minutes=1500)
        self._run()
        subjects = sorted(m.subject for m in mail.outbox)
        self.assertEqual(
            subjects,
            ['You left items in your cart', 'Your cart is still waiting'],
        )
        # Both steps recorded exactly once — a re-send of step 1 would show up
        # here as a duplicated index.
        cart.refresh_from_db()
        self.assertEqual(cart.metadata.get('recovery_drip_sent'), [0, 1])

    # ── (c) idempotency ───────────────────────────────────────────────────────

    def test_rerun_does_not_resend(self):
        self._consent(marketing=True)
        cart = self._cart(age_minutes=90)
        self._run()
        self.assertEqual(len(mail.outbox), 1)
        mail.outbox.clear()
        # Re-run with the same cart state: step 1 is already recorded.
        self._run()
        self.assertEqual(len(mail.outbox), 0)
        cart.refresh_from_db()
        self.assertEqual(cart.metadata.get('recovery_drip_sent'), [0])

    # ── (c2) M1 regression: detection must not reset the drip clock ────────────

    def test_scan_then_drip_step1_still_fires(self):
        """Detection (scan_abandoned_carts) bumped Cart.updated_at via auto_now,
        which reset the drip's age and starved step 1. After the fix the scan
        no longer bumps updated_at and the drip ages off the stable
        'abandoned_emitted' anchor, so step 1 fires on schedule.

        FAILS against the old updated_at-bump + updated_at-anchored behaviour
        (the scan resets the clock → 0 emails); PASSES after the fix.
        """
        self._consent(marketing=True)
        # A cart last active 90 min ago — old enough for detection and step 1.
        cart = self._cart(age_minutes=90)

        fired = self._scan()
        self.assertEqual(fired['fired'], 1)
        cart.refresh_from_db()
        self.assertIn('abandoned_emitted', cart.metadata)

        # 90 min have since passed since detection stamped the cart — well past
        # step 1's 60-min delay. Backdate the anchor to model that wall-clock
        # gap (updated_at is left untouched, as the fixed scan leaves it).
        self._set_abandoned_emitted(cart, minutes_ago=90)

        self._run()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'You left items in your cart')
        cart.refresh_from_db()
        self.assertEqual(cart.metadata.get('recovery_drip_sent'), [0])

    # ── (c3) M2 regression: a 4th delay with no template never sends/records ───

    def test_extra_delay_without_template_never_sends(self):
        """step_delays_minutes can be longer than the 3 defined templates. A 4th
        step has no cart_recovery_4 template; send_templated_email is silent on
        a missing key, so the old loop marked it 'sent' though nothing shipped.
        After the fix step index 3 is never sent and never recorded.
        """
        from unittest import mock

        # Old enough that ALL four configured delays have elapsed.
        cart = self._cart(age_minutes=99999)
        cfg = {
            'recovery_enabled': True,
            'step_delays_minutes': [60, 1440, 4320, 9999],
            'require_marketing_consent': False,
        }
        with mock.patch('plugins.installed.cart_abandonment.tasks._config', return_value=cfg):
            self._run()

        # Exactly the 3 templated steps shipped — not the phantom 4th.
        self.assertEqual(len(mail.outbox), 3)
        cart.refresh_from_db()
        sent = cart.metadata.get('recovery_drip_sent')
        self.assertEqual(sent, [0, 1, 2])
        self.assertNotIn(3, sent)

    # ── (d) marketing consent ─────────────────────────────────────────────────

    def test_no_email_without_marketing_consent(self):
        self._consent(marketing=False)
        self._cart(age_minutes=90)
        self._run()
        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_with_no_consent_row(self):
        # No ConsentLog at all → treated as no consent.
        self._cart(age_minutes=90)
        self._run()
        self.assertEqual(len(mail.outbox), 0)

    def test_email_with_marketing_consent_true(self):
        self._consent(marketing=True)
        self._cart(age_minutes=90)
        self._run()
        self.assertEqual(len(mail.outbox), 1)

    def test_latest_consent_row_wins(self):
        # Older yes, newer no → no email.
        self._consent(marketing=True)
        self._consent(marketing=False)
        self._cart(age_minutes=90)
        self._run()
        self.assertEqual(len(mail.outbox), 0)

    # ── (e) recovered-cart guard ──────────────────────────────────────────────

    def test_empty_cart_gets_no_email(self):
        self._consent(marketing=True)
        self._cart(with_item=False, age_minutes=90)
        self._run()
        self.assertEqual(len(mail.outbox), 0)

    # ── consent toggle off ────────────────────────────────────────────────────

    def test_consent_not_required_sends_without_a_row(self):
        from unittest import mock

        cart = self._cart(age_minutes=90)
        cfg = {
            'recovery_enabled': True,
            'step_delays_minutes': [60, 1440, 4320],
            'require_marketing_consent': False,
        }
        with mock.patch('plugins.installed.cart_abandonment.tasks._config', return_value=cfg):
            self._run()
        self.assertEqual(len(mail.outbox), 1)
        cart.refresh_from_db()
        self.assertEqual(cart.metadata.get('recovery_drip_sent'), [0])

    def test_recovery_disabled_sends_nothing(self):
        from unittest import mock

        self._consent(marketing=True)
        self._cart(age_minutes=90)
        cfg = {
            'recovery_enabled': False,
            'step_delays_minutes': [60, 1440, 4320],
            'require_marketing_consent': True,
        }
        with mock.patch('plugins.installed.cart_abandonment.tasks._config', return_value=cfg):
            self._run()
        self.assertEqual(len(mail.outbox), 0)


class SingleSenderInvariantTests(TestCase):
    """(f) Exactly one recovery-email code path remains.

    core/emails and marketing must no longer register an email handler on
    CART_ABANDONED. crm / ai_assistant / self_improvement may still
    subscribe — those are non-email follow-ups and are explicitly kept.
    """

    def test_core_emails_no_longer_registers_cart_abandoned(self):
        from core.emails import handlers

        self.assertFalse(hasattr(handlers, 'on_cart_abandoned'))

    def test_marketing_no_longer_has_recovery_task(self):
        from plugins.installed.marketing import tasks as marketing_tasks

        self.assertFalse(hasattr(marketing_tasks, 'trigger_cart_recovery_sequence'))

    def test_marketing_plugin_no_longer_handles_cart_abandoned(self):
        from plugins.installed.marketing.app import MarketingPlugin

        self.assertFalse(hasattr(MarketingPlugin, 'on_cart_abandoned'))

    def test_registered_cart_abandoned_handlers_exclude_retired_senders(self):
        from core.emails.handlers import register_handlers
        from morpheus.core import events, hook_registry

        # Force core's idempotent email-handler registration so the registry
        # reflects the post-refactor wiring even in an isolated run.
        register_handlers()

        names = []
        for _priority, handler, *_ in hook_registry._handlers.get(events.CART_ABANDONED, []):
            mod = getattr(handler, '__module__', '')
            qual = getattr(handler, '__qualname__', getattr(handler, '__name__', ''))
            names.append(f'{mod}.{qual}')

        # Retired senders are gone from the cart.abandoned chain…
        self.assertNotIn('core.emails.handlers.on_cart_abandoned', names)
        for n in names:
            self.assertFalse(
                n.startswith('plugins.installed.marketing.'),
                f'marketing should not handle CART_ABANDONED: {n}',
            )
