"""Member perks require evidence of PAYMENT, not just an entitling state.

Until v0.40 the storefront subscribe view created a Subscription with
``state='active'`` and never touched payment, while the cart discount keyed
entitlement off that state string alone. Any logged-in customer could POST
``/membership/subscribe/`` and take the member discount off every order,
forever, having paid nothing.

Checking for payment evidence rather than trusting the state also de-entitles
the rows that were already minted that way — no data migration needed — and
means the next code path that writes 'active' cannot silently reopen the hole.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.subscriptions.membership import member_discount_percent
from plugins.installed.subscriptions.models import Plan, Subscription, SubscriptionInvoice


def _usd(n):
    return Money(Decimal(str(n)), 'USD')


class MemberEntitlementTests(TestCase):
    def setUp(self):
        self.customer = get_user_model().objects.create_user(
            username='member', email='m@example.com', password='x'
        )
        self.paid_plan = Plan.objects.create(
            name='Gold', slug='gold', price=_usd(5), member_discount_percent=20
        )
        self.free_plan = Plan.objects.create(
            name='Free', slug='free', price=_usd(0), member_discount_percent=10
        )

    def _sub(self, plan, **kw):
        return Subscription.objects.create(
            customer=self.customer, plan=plan, current_period_start=timezone.now(), **kw
        )

    # ── The leak ─────────────────────────────────────────────────────────────

    def test_active_without_any_payment_evidence_is_not_entitled(self):
        # Exactly the row the old subscribe view minted: paid plan, 'active',
        # no provider subscription, no invoice — nobody ever charged for it.
        self._sub(self.paid_plan, state='active')
        self.assertEqual(member_discount_percent(self.customer), 0)

    def test_trialing_without_payment_evidence_is_not_entitled(self):
        self._sub(self.paid_plan, state='trialing')
        self.assertEqual(member_discount_percent(self.customer), 0)

    # ── Legitimate members still get their perk ──────────────────────────────

    def test_free_plan_is_entitled(self):
        # Nothing to pay, so an active row is genuine.
        self._sub(self.free_plan, state='active')
        self.assertEqual(member_discount_percent(self.customer), 10)

    def test_provider_subscription_is_entitled(self):
        # Stripe holds a verified card and owns the dunning ladder.
        self._sub(self.paid_plan, state='active', provider_subscription_id='sub_123')
        self.assertEqual(member_discount_percent(self.customer), 20)

    def test_paid_invoice_is_entitled(self):
        # Offline billing the merchant recorded.
        sub = self._sub(self.paid_plan, state='active')
        SubscriptionInvoice.objects.create(
            subscription=sub,
            period_start=timezone.now(),
            period_end=timezone.now(),
            amount=_usd(5),
            state='paid',
        )
        self.assertEqual(member_discount_percent(self.customer), 20)

    def test_unpaid_invoice_is_not_evidence(self):
        sub = self._sub(self.paid_plan, state='active')
        SubscriptionInvoice.objects.create(
            subscription=sub,
            period_start=timezone.now(),
            period_end=timezone.now(),
            amount=_usd(5),
            state='open',
        )
        self.assertEqual(member_discount_percent(self.customer), 0)

    # ── Non-entitling states stay non-entitling even when paid ───────────────

    def test_past_due_is_not_entitled(self):
        self._sub(self.paid_plan, state='past_due', provider_subscription_id='sub_x')
        self.assertEqual(member_discount_percent(self.customer), 0)

    def test_cancelled_is_not_entitled(self):
        self._sub(self.paid_plan, state='cancelled', provider_subscription_id='sub_x')
        self.assertEqual(member_discount_percent(self.customer), 0)

    def test_best_of_several_entitling_plans_wins(self):
        self._sub(self.free_plan, state='active')
        self._sub(self.paid_plan, state='active', provider_subscription_id='sub_9')
        self.assertEqual(member_discount_percent(self.customer), 20)

    def test_anonymous_gets_nothing(self):
        self.assertEqual(member_discount_percent(None), 0)


class SubscribeViewTests(TestCase):
    """The signup path must not hand out paid memberships for nothing."""

    def setUp(self):
        self.customer = get_user_model().objects.create_user(
            username='shopper2', email='s2@example.com', password='pw'
        )
        self.client.force_login(self.customer)
        self.paid = Plan.objects.create(
            name='Gold2', slug='gold2', price=_usd(5), member_discount_percent=20
        )
        self.free = Plan.objects.create(
            name='Free2', slug='free2', price=_usd(0), member_discount_percent=10
        )

    def test_paid_plan_signup_creates_nothing(self):
        resp = self.client.post('/membership/subscribe/', {'plan_id': str(self.paid.id)})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Subscription.objects.filter(customer=self.customer).exists())
        self.assertEqual(member_discount_percent(self.customer), 0)

    def test_free_plan_signup_still_works(self):
        self.client.post('/membership/subscribe/', {'plan_id': str(self.free.id)})
        sub = Subscription.objects.get(customer=self.customer)
        self.assertEqual(sub.state, 'active')
        self.assertEqual(member_discount_percent(self.customer), 10)
