"""Subscription agent commands — Linda can list + pause/resume/cancel subs."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.subscriptions.agent_tools import (
    subscriptions_cancel_tool,
    subscriptions_list_tool,
    subscriptions_pause_tool,
    subscriptions_resume_tool,
)
from plugins.installed.subscriptions.app import SubscriptionsPlugin
from plugins.installed.subscriptions.models import Plan, Subscription


class SubscriptionAgentToolTests(TestCase):
    def setUp(self):
        self.cust = get_user_model().objects.create_user(
            username='sub', email='sub@example.test', password='pw'
        )
        from djmoney.money import Money

        self.plan = Plan.objects.create(
            name='Monthly Box', slug='monthly-box', price=Money(10, 'USD')
        )
        self.sub = Subscription.objects.create(customer=self.cust, plan=self.plan, state='active')

    def test_plugin_contributes_four_tools(self):
        names = {t.name for t in SubscriptionsPlugin().contribute_agent_tools()}
        self.assertEqual(
            names,
            {
                'subscriptions.list',
                'subscriptions.pause',
                'subscriptions.resume',
                'subscriptions.cancel',
            },
        )

    def test_list_filters_by_email(self):
        out = subscriptions_list_tool.invoke({'email': 'sub@example.test'}).output
        self.assertEqual(out['count'], 1)
        self.assertEqual(out['subscriptions'][0]['plan'], 'Monthly Box')

    def test_pause_then_resume(self):
        paused = subscriptions_pause_tool.invoke({'subscription_id': str(self.sub.id)}).output
        self.assertEqual(paused['state'], 'paused')
        resumed = subscriptions_resume_tool.invoke({'subscription_id': str(self.sub.id)}).output
        self.assertEqual(resumed['state'], 'active')

    def test_pause_invalid_state_errors(self):
        self.sub.state = 'cancelled'
        self.sub.save(update_fields=['state'])
        out = subscriptions_pause_tool.invoke({'subscription_id': str(self.sub.id)}).output
        self.assertIn('error', out)

    def test_cancel_at_period_end_default(self):
        out = subscriptions_cancel_tool.invoke({'subscription_id': str(self.sub.id)}).output
        self.assertTrue(out['cancel_at_period_end'])
        self.assertEqual(out['state'], 'active')  # still active until period end

    def test_cancel_immediately(self):
        out = subscriptions_cancel_tool.invoke(
            {'subscription_id': str(self.sub.id), 'at_period_end': False}
        ).output
        self.assertEqual(out['state'], 'cancelled')

    def test_cancel_scope_is_orders_cancel(self):
        self.assertEqual(subscriptions_cancel_tool.scopes, ['orders.cancel'])
