"""Tests for the Stripe subscription billing adapter.

The ``stripe`` SDK is mocked at the ``stripe.*`` boundary (matching the
payments plugin's test style), so these exercise *our* logic — Product/Price
sync + idempotency, the customer-ensure + subscription-create wiring, the
Stripe-status→local-state mapping, period extraction, and the never-raise
fail-soft contract — not Stripe's network layer.

The Stripe secret key is supplied by mocking ``PaymentService.get_stripe_api_key``
(the same service-layer accessor the adapter reads through), so no real key is
needed and the fail-soft branch is testable by returning ``''``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import stripe
from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.subscriptions.billing import StripeSubscriptionAdapter
from plugins.installed.subscriptions.models import Plan, Subscription

_KEY_ACCESSOR = 'plugins.installed.payments.services.stripe.PaymentService.get_stripe_api_key'


def _plan(**kw):
    defaults = {
        'name': 'Book Box',
        'slug': 'book-box',
        'price': Money(10, 'USD'),
        'provider': 'stripe',
        'interval': 'month',
        'interval_count': 1,
    }
    defaults.update(kw)
    return Plan.objects.create(**defaults)


def _customer(**kw):
    defaults = {'username': 'sub', 'email': 'sub@example.test', 'password': 'pw'}
    defaults.update(kw)
    return get_user_model().objects.create_user(**defaults)


class SyncPlanTests(TestCase):
    def setUp(self):
        patcher = mock.patch(_KEY_ACCESSOR, return_value='sk_test_dummy')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_creates_and_stores_price_when_blank(self):
        plan = _plan()  # provider_price_id blank
        with (
            mock.patch('stripe.Product.create', return_value=SimpleNamespace(id='prod_1')) as prod,
            mock.patch('stripe.Price.create', return_value=SimpleNamespace(id='price_1')) as price,
        ):
            result = StripeSubscriptionAdapter.sync_plan(plan)

        self.assertEqual(result, 'price_1')
        plan.refresh_from_db()
        self.assertEqual(plan.provider_price_id, 'price_1')

        prod.assert_called_once()
        price.assert_called_once()
        kwargs = price.call_args.kwargs
        self.assertEqual(kwargs['product'], 'prod_1')
        self.assertEqual(kwargs['unit_amount'], 1000)  # $10.00 → cents
        self.assertEqual(kwargs['currency'], 'usd')
        self.assertEqual(kwargs['recurring'], {'interval': 'month', 'interval_count': 1})

    def test_idempotent_when_already_synced(self):
        plan = _plan(provider_price_id='price_existing')
        with (
            mock.patch('stripe.Product.create') as prod,
            mock.patch('stripe.Price.create') as price,
        ):
            result = StripeSubscriptionAdapter.sync_plan(plan)

        self.assertEqual(result, 'price_existing')
        prod.assert_not_called()
        price.assert_not_called()

    def test_zero_decimal_currency_sends_whole_units(self):
        plan = _plan(slug='yen-box', price=Money(1000, 'JPY'))
        with (
            mock.patch('stripe.Product.create', return_value=SimpleNamespace(id='prod_j')),
            mock.patch('stripe.Price.create', return_value=SimpleNamespace(id='price_j')) as price,
        ):
            StripeSubscriptionAdapter.sync_plan(plan)

        kwargs = price.call_args.kwargs
        self.assertEqual(kwargs['unit_amount'], 1000)  # JPY exponent 0 → no ×100
        self.assertEqual(kwargs['currency'], 'jpy')


class SyncPlanProviderTests(TestCase):
    def test_manual_plan_returns_empty_without_stripe_call(self):
        plan = _plan(slug='manual', provider='manual')
        with (
            mock.patch(_KEY_ACCESSOR, return_value='sk_test_dummy'),
            mock.patch('stripe.Product.create') as prod,
            mock.patch('stripe.Price.create') as price,
        ):
            self.assertEqual(StripeSubscriptionAdapter.sync_plan(plan), '')
        prod.assert_not_called()
        price.assert_not_called()

    def test_missing_key_fails_soft(self):
        plan = _plan(slug='nokey')
        with (
            mock.patch(_KEY_ACCESSOR, return_value=''),
            mock.patch('stripe.Product.create') as prod,
            self.assertLogs('morpheus.subscriptions.stripe', level='WARNING'),
        ):
            self.assertEqual(StripeSubscriptionAdapter.sync_plan(plan), '')
        prod.assert_not_called()
        plan.refresh_from_db()
        self.assertEqual(plan.provider_price_id, '')


class StartSubscriptionTests(TestCase):
    def setUp(self):
        patcher = mock.patch(_KEY_ACCESSOR, return_value='sk_test_dummy')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cust = _customer()
        self.plan = _plan(provider_price_id='price_123', trial_days=0)
        self.sub = Subscription.objects.create(customer=self.cust, plan=self.plan, state='trialing')

    def _fake_stripe_sub(self, **kw):
        defaults = {
            'id': 'sub_1',
            'status': 'active',
            'current_period_start': 1_700_000_000,
            'current_period_end': 1_702_592_000,
        }
        defaults.update(kw)
        return SimpleNamespace(**defaults)

    def test_happy_path_ensures_customer_and_stores_provider_and_periods(self):
        with (
            mock.patch(
                'stripe.Customer.create', return_value=SimpleNamespace(id='cus_1')
            ) as cus_create,
            mock.patch('stripe.PaymentMethod.attach') as attach,
            mock.patch('stripe.Customer.modify') as cus_modify,
            mock.patch(
                'stripe.Subscription.create', return_value=self._fake_stripe_sub()
            ) as sub_create,
        ):
            result = StripeSubscriptionAdapter.start_subscription(self.sub, 'pm_1')

        self.assertEqual(result, {'success': True, 'provider_subscription_id': 'sub_1'})

        # Customer ensured through the payments service (vault created + stored).
        cus_create.assert_called_once()
        self.cust.refresh_from_db()
        self.assertEqual(self.cust.stripe_customer_id, 'cus_1')

        # PM attached + set as invoice default.
        attach.assert_called_once_with('pm_1', customer='cus_1')
        cus_modify.assert_called_once_with(
            'cus_1', invoice_settings={'default_payment_method': 'pm_1'}
        )

        # Subscription created with the synced price + linkage metadata.
        kwargs = sub_create.call_args.kwargs
        self.assertEqual(kwargs['customer'], 'cus_1')
        self.assertEqual(kwargs['items'], [{'price': 'price_123'}])
        self.assertEqual(kwargs['default_payment_method'], 'pm_1')
        self.assertEqual(kwargs['metadata'], {'subscription_id': str(self.sub.id)})
        self.assertNotIn('trial_period_days', kwargs)  # trial_days == 0

        # Provider id + mapped state + periods mirrored locally.
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.provider_subscription_id, 'sub_1')
        self.assertEqual(self.sub.state, 'active')
        self.assertIsNotNone(self.sub.current_period_start)
        self.assertIsNotNone(self.sub.current_period_end)
        self.assertEqual(self.sub.current_period_end.year, 2023)

    def test_trial_days_forwarded_and_state_mapped(self):
        self.plan.trial_days = 14
        self.plan.save(update_fields=['trial_days'])
        self.cust.stripe_customer_id = 'cus_pre'
        self.cust.save(update_fields=['stripe_customer_id'])

        with (
            mock.patch('stripe.PaymentMethod.attach'),
            mock.patch('stripe.Customer.modify'),
            mock.patch(
                'stripe.Subscription.create',
                return_value=self._fake_stripe_sub(status='trialing'),
            ) as sub_create,
        ):
            StripeSubscriptionAdapter.start_subscription(self.sub, 'pm_1')

        self.assertEqual(sub_create.call_args.kwargs['trial_period_days'], 14)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.state, 'trialing')

    def test_period_read_from_subscription_items_fallback(self):
        # Post-basil Stripe API: the period lives on the item, not the sub.
        self.cust.stripe_customer_id = 'cus_pre'
        self.cust.save(update_fields=['stripe_customer_id'])
        item = SimpleNamespace(current_period_start=1_700_000_000, current_period_end=1_702_592_000)
        stripe_sub = SimpleNamespace(
            id='sub_items',
            status='active',
            current_period_start=None,
            current_period_end=None,
            items=SimpleNamespace(data=[item]),
        )
        with (
            mock.patch('stripe.PaymentMethod.attach'),
            mock.patch('stripe.Customer.modify'),
            mock.patch('stripe.Subscription.create', return_value=stripe_sub),
        ):
            StripeSubscriptionAdapter.start_subscription(self.sub, 'pm_1')

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.current_period_end.year, 2023)

    def test_stripe_error_returns_success_false_no_crash(self):
        self.cust.stripe_customer_id = 'cus_pre'
        self.cust.save(update_fields=['stripe_customer_id'])
        err = stripe.error.APIError('stripe is down')
        with (
            mock.patch('stripe.PaymentMethod.attach'),
            mock.patch('stripe.Customer.modify'),
            mock.patch('stripe.Subscription.create', side_effect=err),
            self.assertLogs('morpheus.subscriptions.stripe', level='WARNING'),
        ):
            result = StripeSubscriptionAdapter.start_subscription(self.sub, 'pm_1')

        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.provider_subscription_id, '')  # nothing stored
        self.assertEqual(self.sub.state, 'trialing')  # untouched

    def test_missing_key_fails_soft(self):
        with (
            mock.patch(_KEY_ACCESSOR, return_value=''),
            mock.patch('stripe.Subscription.create') as create,
            self.assertLogs('morpheus.subscriptions.stripe', level='WARNING'),
        ):
            result = StripeSubscriptionAdapter.start_subscription(self.sub, 'pm_1')

        self.assertFalse(result['success'])
        create.assert_not_called()


class CancelPauseResumeTests(TestCase):
    def setUp(self):
        patcher = mock.patch(_KEY_ACCESSOR, return_value='sk_test_dummy')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cust = _customer()
        self.plan = _plan(provider_price_id='price_123')
        self.sub = Subscription.objects.create(
            customer=self.cust,
            plan=self.plan,
            state='active',
            provider_subscription_id='sub_live',
        )

    def test_cancel_at_period_end_mirrors_flag(self):
        with mock.patch('stripe.Subscription.modify') as modify:
            result = StripeSubscriptionAdapter.cancel_subscription(self.sub, at_period_end=True)

        self.assertTrue(result['success'])
        modify.assert_called_once_with('sub_live', cancel_at_period_end=True)
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.cancel_at_period_end)
        self.assertEqual(self.sub.state, 'active')  # keeps access until period end

    def test_cancel_immediately_deletes_and_marks_cancelled(self):
        with mock.patch('stripe.Subscription.delete') as delete:
            result = StripeSubscriptionAdapter.cancel_subscription(self.sub, at_period_end=False)

        self.assertTrue(result['success'])
        delete.assert_called_once_with('sub_live')
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.state, 'cancelled')
        self.assertIsNotNone(self.sub.cancelled_at)

    def test_cancel_stripe_error_does_not_mirror(self):
        with mock.patch('stripe.Subscription.modify', side_effect=stripe.error.APIError('boom')):
            result = StripeSubscriptionAdapter.cancel_subscription(self.sub, at_period_end=True)

        self.assertFalse(result['success'])
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.cancel_at_period_end)  # not mirrored on failure

    def test_pause_then_resume(self):
        with mock.patch('stripe.Subscription.modify') as modify:
            StripeSubscriptionAdapter.pause_subscription(self.sub)
            self.sub.refresh_from_db()
            self.assertEqual(self.sub.state, 'paused')
            self.assertEqual(modify.call_args.kwargs['pause_collection'], {'behavior': 'void'})

            StripeSubscriptionAdapter.resume_subscription(self.sub)
            self.sub.refresh_from_db()
            self.assertEqual(self.sub.state, 'active')
            self.assertEqual(modify.call_args.kwargs['pause_collection'], '')
