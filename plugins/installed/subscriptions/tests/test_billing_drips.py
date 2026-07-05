"""Dunning + pre-renewal drip tests.

``send_templated_email`` is mocked (per the spec) so these assert *our*
scheduling/idempotency/consent logic — step timing off the metadata anchor,
once-per-period renewal marker, and the marketing-consent gate — not the email
render/transport.
"""

from __future__ import annotations

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.consent.models import ConsentLog
from plugins.installed.subscriptions.models import Plan, Subscription
from plugins.installed.subscriptions.tasks import send_dunning_emails, send_renewal_reminders

_SEND = 'core.emails.send_templated_email'


class _Base(TestCase):
    def setUp(self):
        self.cust = get_user_model().objects.create_user(
            username='m', email='m@example.test', password='pw'
        )
        self.plan = Plan.objects.create(
            name='Book Box', slug='book-box', price=Money(10, 'USD'), provider='stripe'
        )

    def _consent(self, marketing=True):
        ConsentLog.objects.create(customer=self.cust, session_key='s', marketing=marketing)

    def _sub(self, **kw):
        defaults = {
            'customer': self.cust,
            'plan': self.plan,
            'provider_subscription_id': 'sub_x',
        }
        defaults.update(kw)
        return Subscription.objects.create(**defaults)

    def _past_due(self, *, anchor_days_ago=0, sent=None):
        anchor = (timezone.now() - timedelta(days=anchor_days_ago)).isoformat()
        return self._sub(
            state='past_due', metadata={'dunning': {'anchor': anchor, 'sent': list(sent or [])}}
        )

    def _active(self, *, period_end_in_days, **kw):
        end = timezone.now() + timedelta(days=period_end_in_days)
        return self._sub(state='active', current_period_end=end, **kw)


class DunningTests(_Base):
    @mock.patch(_SEND)
    def test_step0_sends_once_and_not_again_same_day(self, send):
        self._consent()
        sub = self._past_due(anchor_days_ago=0)

        send_dunning_emails()
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.kwargs['key'], 'subscription_payment_failed')
        self.assertEqual(send.call_args.kwargs['to'], 'm@example.test')
        sub.refresh_from_db()
        self.assertEqual(sub.metadata['dunning']['sent'], [0])

        send_dunning_emails()  # same day → step 0 already sent, step 1 not due
        self.assertEqual(send.call_count, 1)

    @mock.patch(_SEND)
    def test_step1_due_after_three_days(self, send):
        self._consent()
        sub = self._past_due(anchor_days_ago=3, sent=[0])

        send_dunning_emails()
        self.assertEqual(send.call_count, 1)  # only step 1 (day 3); step 2 (day 7) not due
        sub.refresh_from_db()
        self.assertEqual(sub.metadata['dunning']['sent'], [0, 1])

    @mock.patch(_SEND)
    def test_no_send_without_marketing_consent(self, send):
        self._past_due(anchor_days_ago=0)  # no consent row
        send_dunning_emails()
        send.assert_not_called()

    @mock.patch(_SEND)
    def test_consent_false_blocks_send(self, send):
        self._consent(marketing=False)
        self._past_due(anchor_days_ago=0)
        send_dunning_emails()
        send.assert_not_called()

    @mock.patch(_SEND)
    def test_non_past_due_subscription_is_skipped(self, send):
        self._consent()
        # An active sub with a stale marker must not be dunned (queryset gate).
        self._sub(
            state='active', metadata={'dunning': {'anchor': timezone.now().isoformat(), 'sent': []}}
        )
        send_dunning_emails()
        send.assert_not_called()

    @mock.patch(_SEND)
    def test_anchor_falls_back_to_open_invoice(self, send):
        from plugins.installed.subscriptions.models import SubscriptionInvoice

        self._consent()
        sub = self._sub(state='past_due', metadata={})  # no dunning marker
        SubscriptionInvoice.objects.create(
            subscription=sub,
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30),
            amount=Money(10, 'USD'),
            state='open',
        )
        send_dunning_emails()
        self.assertEqual(send.call_count, 1)  # step 0 due off the invoice timestamp


class PreRenewalTests(_Base):
    @mock.patch(_SEND)
    def test_sends_once_per_period(self, send):
        self._consent()
        sub = self._active(period_end_in_days=2)  # within default 3-day window

        send_renewal_reminders()
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.kwargs['key'], 'subscription_upcoming_renewal')
        sub.refresh_from_db()
        self.assertIn('renewal_notified', sub.metadata)

        send_renewal_reminders()  # same period → idempotent
        self.assertEqual(send.call_count, 1)

    @mock.patch(_SEND)
    def test_skips_outside_prerenewal_window(self, send):
        self._consent()
        self._active(period_end_in_days=10)  # > 3 days out
        send_renewal_reminders()
        send.assert_not_called()

    @mock.patch(_SEND)
    def test_new_period_reminds_again(self, send):
        self._consent()
        sub = self._active(period_end_in_days=2)
        send_renewal_reminders()
        self.assertEqual(send.call_count, 1)

        # A new billing cycle → different current_period_end → new marker.
        Subscription.objects.filter(pk=sub.pk).update(
            current_period_end=timezone.now() + timedelta(days=1, hours=6)
        )
        send_renewal_reminders()
        self.assertEqual(send.call_count, 2)

    @mock.patch(_SEND)
    def test_cancelling_subscription_gets_no_reminder(self, send):
        self._consent()
        self._active(period_end_in_days=2, cancel_at_period_end=True)
        send_renewal_reminders()
        send.assert_not_called()

    @mock.patch(_SEND)
    def test_respects_consent(self, send):
        self._active(period_end_in_days=2)  # no consent
        send_renewal_reminders()
        send.assert_not_called()
