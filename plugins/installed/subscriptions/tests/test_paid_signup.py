"""Paid membership sign-up — the Stripe card-collection leg (P4a part 2).

The properties that matter, in order of what would go wrong without them:

* a paid plan is only sold online when it is a Stripe plan AND Stripe is
  configured on both ends; otherwise it is refused honestly (as before);
* the SetupIntent id Stripe hands back in the URL is caller-supplied — it must
  be *succeeded* and belong to *this* customer before its card is trusted;
* a failed start never leaves a "member" row behind;
* a successful start creates a subscription that `entitling_subscriptions`
  recognises (provider id present) — the discount follows the money.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.subscriptions.billing import StripeSubscriptionAdapter
from plugins.installed.subscriptions.membership import entitling_subscriptions
from plugins.installed.subscriptions.models import Plan, Subscription

_KEY = 'plugins.installed.subscriptions.billing.stripe_adapter._stripe_key'
_VIEW_KEY = 'plugins.installed.subscriptions.views_storefront._stripe_signup_available'


def _plan(**kw):
    defaults = {
        'name': 'Reader',
        'slug': kw.pop('slug', 'reader'),
        'price': Money(5, 'USD'),
        'interval': 'month',
        'provider': 'stripe',
        'member_discount_percent': 10,
    }
    defaults.update(kw)
    return Plan.objects.create(**defaults)


class _Base(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='m', email='m@example.test', password='pw'
        )
        self.user.stripe_customer_id = 'cus_me'
        self.user.save(update_fields=['stripe_customer_id'])
        self.client.force_login(self.user)


@override_settings(STRIPE_PUBLIC_KEY='pk_test_x')
class MembershipPageTests(_Base):
    def test_paid_stripe_plan_offers_the_card_flow_when_stripe_is_configured(self):
        plan = _plan()
        with mock.patch(_KEY, return_value='sk_test_x'):
            r = self.client.get('/membership/')
        self.assertContains(r, f'/membership/subscribe/{plan.id}/')
        self.assertContains(r, 'data-signup="stripe"')

    def test_paid_plan_is_marked_unavailable_without_stripe(self):
        _plan()
        with mock.patch(_KEY, return_value=''):
            r = self.client.get('/membership/')
        self.assertContains(r, 'data-signup="unavailable"')
        self.assertNotContains(r, 'data-signup="stripe"')

    def test_paid_manual_plan_is_unavailable_even_with_stripe(self):
        _plan(provider='manual')
        with mock.patch(_KEY, return_value='sk_test_x'):
            r = self.client.get('/membership/')
        self.assertContains(r, 'data-signup="unavailable"')

    def test_free_plan_keeps_the_immediate_post_form(self):
        _plan(price=Money(0, 'USD'))
        with mock.patch(_KEY, return_value='sk_test_x'):
            r = self.client.get('/membership/')
        self.assertContains(r, 'action="/membership/subscribe/"')
        self.assertNotContains(r, 'data-signup="stripe"')


@override_settings(STRIPE_PUBLIC_KEY='pk_test_x')
class SubscribeViewRoutingTests(_Base):
    def test_free_plan_activates_immediately(self):
        plan = _plan(price=Money(0, 'USD'))
        r = self.client.post('/membership/subscribe/', {'plan_id': str(plan.id)})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Subscription.objects.filter(customer=self.user, state='active').exists())

    def test_paid_stripe_plan_redirects_to_card_collection(self):
        plan = _plan()
        with mock.patch(_KEY, return_value='sk_test_x'):
            r = self.client.post('/membership/subscribe/', {'plan_id': str(plan.id)})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], f'/membership/subscribe/{plan.id}/')
        self.assertFalse(Subscription.objects.exists(), 'nothing is created before the card leg')

    def test_paid_plan_without_stripe_is_refused_and_creates_nothing(self):
        plan = _plan()
        with mock.patch(_KEY, return_value=''):
            r = self.client.post('/membership/subscribe/', {'plan_id': str(plan.id)}, follow=True)
        self.assertContains(r, 'not available yet')
        self.assertFalse(Subscription.objects.exists())


@override_settings(STRIPE_PUBLIC_KEY='pk_test_x')
class SubscribeStartTests(_Base):
    def test_mounts_a_payment_element_on_a_setup_intent(self):
        plan = _plan()
        with (
            mock.patch(_KEY, return_value='sk_test_x'),
            mock.patch(
                'plugins.installed.payments.services.stripe.create_setup_intent',
                return_value='seti_1_secret_abc',
            ) as csi,
        ):
            r = self.client.get(f'/membership/subscribe/{plan.id}/')
        self.assertEqual(r.status_code, 200)
        csi.assert_called_once_with(self.user)
        from django.utils.html import escapejs

        self.assertContains(r, 'data-signup-state="ready"')
        self.assertContains(r, 'seti_1_secret_abc')
        # The return URL sits inside the script, `escapejs`'d (`/` → `\\u002F`).
        self.assertContains(
            r, escapejs(f'http://testserver/membership/subscribe/{plan.id}/confirm/')
        )

    def test_setup_intent_failure_degrades_to_a_message_not_a_500(self):
        plan = _plan()
        with (
            mock.patch(_KEY, return_value='sk_test_x'),
            mock.patch(
                'plugins.installed.payments.services.stripe.create_setup_intent',
                side_effect=RuntimeError('stripe down'),
            ),
        ):
            r = self.client.get(f'/membership/subscribe/{plan.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-signup-state="unavailable"')

    def test_free_or_manual_plan_is_not_sold_here(self):
        free = _plan(price=Money(0, 'USD'), slug='free')
        manual = _plan(provider='manual', slug='manual')
        with mock.patch(_KEY, return_value='sk_test_x'):
            for plan in (free, manual):
                r = self.client.get(f'/membership/subscribe/{plan.id}/')
                self.assertEqual(r.status_code, 302, plan.slug)

    def test_existing_member_is_sent_back(self):
        plan = _plan()
        Subscription.objects.create(customer=self.user, plan=plan, state='active')
        with mock.patch(_KEY, return_value='sk_test_x'):
            r = self.client.get(f'/membership/subscribe/{plan.id}/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], '/membership/')

    def test_anonymous_is_sent_to_login(self):
        plan = _plan()
        self.client.logout()
        r = self.client.get(f'/membership/subscribe/{plan.id}/')
        self.assertEqual(r.status_code, 302)
        self.assertNotIn(f'/membership/subscribe/{plan.id}/', r['Location'].split('?')[0])


class SetupIntentVerificationTests(TestCase):
    """`payment_method_from_setup_intent` — the id in the URL is untrusted."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='v', email='v@example.test', password='pw'
        )
        self.user.stripe_customer_id = 'cus_me'
        self.user.save(update_fields=['stripe_customer_id'])
        p = mock.patch(_KEY, return_value='sk_test_x')
        p.start()
        self.addCleanup(p.stop)

    def _intent(self, **kw):
        base = {'status': 'succeeded', 'customer': 'cus_me', 'payment_method': 'pm_ok'}
        base.update(kw)
        return SimpleNamespace(**base)

    def test_succeeded_intent_of_this_customer_yields_its_card(self):
        with mock.patch('stripe.SetupIntent.retrieve', return_value=self._intent()) as ret:
            pm = StripeSubscriptionAdapter.payment_method_from_setup_intent('seti_1', self.user)
        self.assertEqual(pm, 'pm_ok')
        ret.assert_called_once_with('seti_1')

    def test_expanded_payment_method_object_is_handled(self):
        intent = self._intent(payment_method=SimpleNamespace(id='pm_obj'))
        with mock.patch('stripe.SetupIntent.retrieve', return_value=intent):
            pm = StripeSubscriptionAdapter.payment_method_from_setup_intent('seti_1', self.user)
        self.assertEqual(pm, 'pm_obj')

    def test_another_customers_intent_is_refused(self):
        with mock.patch('stripe.SetupIntent.retrieve', return_value=self._intent(customer='cus_x')):
            pm = StripeSubscriptionAdapter.payment_method_from_setup_intent('seti_1', self.user)
        self.assertEqual(pm, '')

    def test_unfinished_intent_is_refused(self):
        with mock.patch(
            'stripe.SetupIntent.retrieve', return_value=self._intent(status='requires_action')
        ):
            pm = StripeSubscriptionAdapter.payment_method_from_setup_intent('seti_1', self.user)
        self.assertEqual(pm, '')

    def test_junk_id_never_reaches_stripe(self):
        with mock.patch('stripe.SetupIntent.retrieve') as ret:
            self.assertEqual(
                StripeSubscriptionAdapter.payment_method_from_setup_intent('pi_1', self.user), ''
            )
            self.assertEqual(
                StripeSubscriptionAdapter.payment_method_from_setup_intent('', self.user), ''
            )
        ret.assert_not_called()

    def test_customer_without_a_vault_is_refused_before_stripe(self):
        self.user.stripe_customer_id = ''
        self.user.save(update_fields=['stripe_customer_id'])
        with mock.patch('stripe.SetupIntent.retrieve') as ret:
            pm = StripeSubscriptionAdapter.payment_method_from_setup_intent('seti_1', self.user)
        self.assertEqual(pm, '')
        ret.assert_not_called()

    def test_stripe_error_is_a_refusal_not_a_crash(self):
        with mock.patch('stripe.SetupIntent.retrieve', side_effect=RuntimeError('boom')):
            pm = StripeSubscriptionAdapter.payment_method_from_setup_intent('seti_1', self.user)
        self.assertEqual(pm, '')


_PM = 'plugins.installed.subscriptions.billing.stripe_adapter.StripeSubscriptionAdapter.payment_method_from_setup_intent'
_START = 'plugins.installed.subscriptions.billing.stripe_adapter.StripeSubscriptionAdapter.start_subscription'


@override_settings(STRIPE_PUBLIC_KEY='pk_test_x')
class SubscribeConfirmTests(_Base):
    def _confirm(self, plan, **query):
        q = {'setup_intent': 'seti_1', 'redirect_status': 'succeeded', **query}
        return self.client.get(f'/membership/subscribe/{plan.id}/confirm/', q, follow=True)

    def _fake_start(self, sub, pm_id):
        # What the real adapter does on success: stores the provider id and
        # mirrors Stripe's status. Everything downstream keys off these.
        sub.provider_subscription_id = 'sub_stripe_1'
        sub.state = 'active'
        sub.save(update_fields=['provider_subscription_id', 'state'])
        return {'success': True, 'provider_subscription_id': 'sub_stripe_1'}

    def test_happy_path_creates_an_entitled_membership(self):
        plan = _plan()
        with (
            mock.patch(_KEY, return_value='sk_test_x'),
            mock.patch(_PM, return_value='pm_ok') as pm,
            mock.patch(_START, side_effect=self._fake_start) as start,
        ):
            r = self._confirm(plan)
        pm.assert_called_once_with('seti_1', self.user)
        self.assertEqual(start.call_count, 1)
        self.assertEqual(start.call_args.args[1], 'pm_ok')
        sub = Subscription.objects.get(customer=self.user)
        self.assertEqual(sub.provider_subscription_id, 'sub_stripe_1')
        self.assertIn(sub, list(entitling_subscriptions(self.user)))
        self.assertContains(r, 'Welcome aboard')

    def test_start_failure_leaves_no_membership_row(self):
        plan = _plan()
        with (
            mock.patch(_KEY, return_value='sk_test_x'),
            mock.patch(_PM, return_value='pm_ok'),
            mock.patch(_START, return_value={'success': False, 'error': 'card declined'}),
        ):
            r = self._confirm(plan)
        self.assertFalse(Subscription.objects.filter(customer=self.user).exists())
        self.assertContains(r, 'card declined')

    def test_unverified_setup_intent_starts_nothing(self):
        plan = _plan()
        with (
            mock.patch(_KEY, return_value='sk_test_x'),
            mock.patch(_PM, return_value=''),
            mock.patch(_START) as start,
        ):
            r = self._confirm(plan)
        start.assert_not_called()
        self.assertFalse(Subscription.objects.exists())
        self.assertContains(r, 'could not confirm your card')

    def test_failed_redirect_status_starts_nothing(self):
        plan = _plan()
        with (
            mock.patch(_KEY, return_value='sk_test_x'),
            mock.patch(_PM) as pm,
            mock.patch(_START) as start,
        ):
            self._confirm(plan, redirect_status='failed')
        pm.assert_not_called()
        start.assert_not_called()
        self.assertFalse(Subscription.objects.exists())

    def test_existing_member_cannot_double_subscribe(self):
        plan = _plan()
        Subscription.objects.create(customer=self.user, plan=plan, state='active')
        with (
            mock.patch(_KEY, return_value='sk_test_x'),
            mock.patch(_PM, return_value='pm_ok'),
            mock.patch(_START) as start,
        ):
            self._confirm(plan)
        start.assert_not_called()
        self.assertEqual(Subscription.objects.filter(customer=self.user).count(), 1)
