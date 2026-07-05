"""Stripe webhook reconciliation tests (the subscriptions billing loop).

Two layers:

* **Unit** — call ``subscriptions.webhooks.handle_stripe_event`` with
  hand-built Stripe event *dicts* (the payload is a plain dict off the wire, so
  no SDK is involved) and assert the local rows are reconciled: periods
  advance, invoices are upserted, state is mirrored, markers are stamped/cleared
  — and that it is idempotent + fail-soft.
* **Wiring** — deliver a non-payment-intent event through the real
  ``PaymentService.process_webhook`` (``construct_event`` mocked) and assert it
  is fanned out to ``STRIPE_WEBHOOK_EVENT`` exactly once, and that a redelivered
  event id is swallowed by the payments idempotency guard (never re-dispatched).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from core.hooks import MorpheusEvents, hook_registry
from plugins.installed.payments.models import StripeWebhookEvent
from plugins.installed.payments.services.stripe import PaymentService
from plugins.installed.subscriptions.models import Plan, Subscription, SubscriptionInvoice
from plugins.installed.subscriptions.webhooks import handle_stripe_event

# 2023-11-14 and 2023-12-14 — used to assert the advanced period.
_START_TS = 1_700_000_000
_END_TS = 1_702_592_000


def _customer(**kw):
    defaults = {'username': 'sub', 'email': 'sub@example.test', 'password': 'pw'}
    defaults.update(kw)
    return get_user_model().objects.create_user(**defaults)


def _invoice_event(event_type, sub_id, *, invoice_id='in_1', amount=1000, currency='usd'):
    return {
        'id': 'evt_test',
        'type': event_type,
        'data': {
            'object': {
                'id': invoice_id,
                'subscription': sub_id,
                'amount_paid': amount,
                'amount_due': amount,
                'currency': currency,
                'lines': {'data': [{'period': {'start': _START_TS, 'end': _END_TS}}]},
            }
        },
    }


def _sub_event(event_type, sub_id, *, status='active', cape=None, periods=True):
    obj = {'id': sub_id, 'status': status}
    if periods:
        obj['current_period_start'] = _START_TS
        obj['current_period_end'] = _END_TS
    if cape is not None:
        obj['cancel_at_period_end'] = cape
    return {'id': 'evt_test', 'type': event_type, 'data': {'object': obj}}


class InvoicePaidTests(TestCase):
    def setUp(self):
        self.cust = _customer()
        self.plan = _plan()
        self.sub = Subscription.objects.create(
            customer=self.cust,
            plan=self.plan,
            state='trialing',
            provider_subscription_id='sub_1',
        )

    def test_advances_period_and_creates_paid_invoice(self):
        ev = _invoice_event('invoice.paid', 'sub_1', invoice_id='in_1', amount=1000)
        handle_stripe_event(event_type='invoice.paid', payload=ev)

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.state, 'active')
        self.assertEqual(self.sub.current_period_start.year, 2023)
        self.assertEqual(self.sub.current_period_end.year, 2023)

        inv = SubscriptionInvoice.objects.get(subscription=self.sub, provider_invoice_id='in_1')
        self.assertEqual(inv.state, 'paid')
        self.assertIsNotNone(inv.paid_at)
        self.assertEqual(inv.amount, Money(10, 'USD'))

    def test_idempotent_on_second_identical_event(self):
        ev = _invoice_event('invoice.paid', 'sub_1', invoice_id='in_1')
        handle_stripe_event(event_type='invoice.paid', payload=ev)
        handle_stripe_event(event_type='invoice.paid', payload=ev)  # re-run

        self.assertEqual(SubscriptionInvoice.objects.filter(subscription=self.sub).count(), 1)

    def test_leaving_past_due_clears_dunning_marker(self):
        self.sub.state = 'past_due'
        self.sub.metadata = {'dunning': {'anchor': timezone.now().isoformat(), 'sent': [0]}}
        self.sub.save(update_fields=['state', 'metadata'])

        handle_stripe_event(
            event_type='invoice.paid',
            payload=_invoice_event('invoice.paid', 'sub_1', invoice_id='in_x'),
        )
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.state, 'active')
        self.assertNotIn('dunning', self.sub.metadata)

    def test_zero_decimal_currency_amount(self):
        ev = _invoice_event(
            'invoice.paid', 'sub_1', invoice_id='in_jpy', amount=1000, currency='jpy'
        )
        handle_stripe_event(event_type='invoice.paid', payload=ev)
        inv = SubscriptionInvoice.objects.get(provider_invoice_id='in_jpy')
        self.assertEqual(inv.amount, Money(1000, 'JPY'))  # exponent 0 → no /100

    def test_unknown_subscription_is_noop(self):
        handle_stripe_event(
            event_type='invoice.paid', payload=_invoice_event('invoice.paid', 'sub_ghost')
        )
        self.assertEqual(SubscriptionInvoice.objects.count(), 0)


class InvoiceFailedTests(TestCase):
    def setUp(self):
        self.cust = _customer()
        self.plan = _plan()
        self.sub = Subscription.objects.create(
            customer=self.cust,
            plan=self.plan,
            state='active',
            provider_subscription_id='sub_1',
        )

    def test_sets_past_due_opens_invoice_and_arms_dunning(self):
        ev = _invoice_event('invoice.payment_failed', 'sub_1', invoice_id='in_f', amount=1000)
        handle_stripe_event(event_type='invoice.payment_failed', payload=ev)

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.state, 'past_due')
        inv = SubscriptionInvoice.objects.get(subscription=self.sub, provider_invoice_id='in_f')
        self.assertEqual(inv.state, 'open')
        # Dunning anchor stamped in metadata (no migration).
        self.assertIn('dunning', self.sub.metadata)
        self.assertIn('anchor', self.sub.metadata['dunning'])
        self.assertEqual(self.sub.metadata['dunning']['sent'], [])

    def test_repeat_failure_keeps_original_anchor(self):
        ev = _invoice_event('invoice.payment_failed', 'sub_1', invoice_id='in_f')
        handle_stripe_event(event_type='invoice.payment_failed', payload=ev)
        self.sub.refresh_from_db()
        first_anchor = self.sub.metadata['dunning']['anchor']

        handle_stripe_event(event_type='invoice.payment_failed', payload=ev)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.metadata['dunning']['anchor'], first_anchor)


class SubscriptionUpdatedDeletedTests(TestCase):
    def setUp(self):
        self.cust = _customer()
        self.plan = _plan()
        self.sub = Subscription.objects.create(
            customer=self.cust,
            plan=self.plan,
            state='active',
            provider_subscription_id='sub_1',
        )

    def test_updated_syncs_state_period_and_cancel_flag(self):
        ev = _sub_event('customer.subscription.updated', 'sub_1', status='past_due', cape=True)
        handle_stripe_event(event_type='customer.subscription.updated', payload=ev)

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.state, 'past_due')  # _map_state
        self.assertTrue(self.sub.cancel_at_period_end)
        self.assertEqual(self.sub.current_period_end.year, 2023)
        self.assertIn('dunning', self.sub.metadata)  # armed on past_due

    def test_updated_back_to_active_clears_dunning(self):
        self.sub.state = 'past_due'
        self.sub.metadata = {'dunning': {'anchor': timezone.now().isoformat(), 'sent': [0]}}
        self.sub.save(update_fields=['state', 'metadata'])

        ev = _sub_event('customer.subscription.updated', 'sub_1', status='active')
        handle_stripe_event(event_type='customer.subscription.updated', payload=ev)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.state, 'active')
        self.assertNotIn('dunning', self.sub.metadata)

    def test_deleted_marks_cancelled(self):
        ev = _sub_event('customer.subscription.deleted', 'sub_1', status='canceled', periods=False)
        handle_stripe_event(event_type='customer.subscription.deleted', payload=ev)

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.state, 'cancelled')
        self.assertIsNotNone(self.sub.cancelled_at)

    def test_deleted_incomplete_expired_maps_to_expired(self):
        ev = _sub_event(
            'customer.subscription.deleted', 'sub_1', status='incomplete_expired', periods=False
        )
        handle_stripe_event(event_type='customer.subscription.deleted', payload=ev)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.state, 'expired')

    def test_unknown_event_type_is_ignored(self):
        ev = _sub_event('customer.subscription.trial_will_end', 'sub_1', status='trialing')
        handle_stripe_event(event_type='customer.subscription.trial_will_end', payload=ev)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.state, 'active')  # untouched

    def test_missing_data_object_is_fail_soft(self):
        handle_stripe_event(event_type='invoice.paid', payload={'type': 'invoice.paid'})
        # No crash, nothing changed.
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.state, 'active')


class _FakeStripeEvent:
    """Stands in for a ``stripe.Event`` for process_webhook (non-PI path reads
    only ``.id`` / ``.type`` / ``.to_dict()``)."""

    def __init__(self, event_id, event_type, obj):
        self.id = event_id
        self.type = event_type
        self.data = SimpleNamespace(object=SimpleNamespace(**obj))
        self._payload = {'id': event_id, 'type': event_type, 'data': {'object': obj}}

    def to_dict(self):
        return self._payload


class WebhookDispatchTests(TestCase):
    """The payments-side wiring: unowned events fan out to STRIPE_WEBHOOK_EVENT,
    idempotently."""

    def setUp(self):
        self.received = []
        self._spy = lambda event_type, payload, **kw: self.received.append((event_type, payload))
        hook_registry.register(MorpheusEvents.STRIPE_WEBHOOK_EVENT, self._spy)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.STRIPE_WEBHOOK_EVENT, self._spy)

    def _deliver(self, event):
        with mock.patch('stripe.Webhook.construct_event', return_value=event):
            return PaymentService.process_webhook(b'{}', 'sig')

    def test_unowned_event_dispatched_to_hook_with_full_payload(self):
        event = _FakeStripeEvent('evt_1', 'invoice.paid', {'id': 'in_1', 'subscription': 'sub_9'})
        self._deliver(event)

        self.assertEqual(len(self.received), 1)
        event_type, payload = self.received[0]
        self.assertEqual(event_type, 'invoice.paid')
        self.assertEqual(payload['data']['object']['subscription'], 'sub_9')

    def test_duplicate_event_id_not_redispatched(self):
        event = _FakeStripeEvent('evt_dup', 'invoice.paid', {'id': 'in_2', 'subscription': 'sub_9'})
        self.assertTrue(self._deliver(event))
        self.assertTrue(self._deliver(event))  # Stripe redelivery

        self.assertEqual(StripeWebhookEvent.objects.count(), 1)
        self.assertEqual(len(self.received), 1)  # fired exactly once

    def test_payment_intent_event_not_dispatched_to_hook(self):
        # payments owns payment_intent.* directly — must NOT hit the hook.
        event = _FakeStripeEvent(
            'evt_pi',
            'payment_intent.succeeded',
            {'id': 'pi_1', 'last_payment_error': None},
        )
        self._deliver(event)
        self.assertEqual(self.received, [])


def _plan(**kw):
    defaults = {
        'name': 'Book Box',
        'slug': 'book-box',
        'price': Money(10, 'USD'),
        'provider': 'stripe',
        'provider_price_id': 'price_1',
    }
    defaults.update(kw)
    return Plan.objects.create(**defaults)
