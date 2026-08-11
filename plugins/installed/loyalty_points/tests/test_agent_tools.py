"""Loyalty agent commands — Linda can read + adjust a customer's points."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.loyalty_points.agent_tools import (
    loyalty_adjust_points_tool,
    loyalty_balance_tool,
)
from plugins.installed.loyalty_points.app import LoyaltyPointsPlugin


class LoyaltyAgentToolTests(TestCase):
    def setUp(self):
        self.cust = get_user_model().objects.create_user(
            username='shopper', email='shopper@example.test', password='pw'
        )

    def test_plugin_contributes_the_tools(self):
        names = {t.name for t in LoyaltyPointsPlugin().contribute_agent_tools()}
        self.assertEqual(names, {'loyalty.balance', 'loyalty.adjust_points'})

    def test_balance_of_new_customer_is_zero(self):
        out = loyalty_balance_tool.invoke({'email': 'shopper@example.test'}).output
        self.assertEqual(out['points'], 0)

    def test_unknown_email_errors(self):
        out = loyalty_balance_tool.invoke({'email': 'nobody@example.test'}).output
        self.assertIn('error', out)

    def test_adjust_adds_and_deducts(self):
        add = loyalty_adjust_points_tool.invoke(
            {'email': 'shopper@example.test', 'points': 100, 'reason': 'goodwill'}
        ).output
        self.assertEqual(add['new_balance'], 100)
        deduct = loyalty_adjust_points_tool.invoke(
            {'email': 'shopper@example.test', 'points': -30}
        ).output
        self.assertEqual(deduct['new_balance'], 70)

    def test_zero_adjustment_rejected(self):
        out = loyalty_adjust_points_tool.invoke(
            {'email': 'shopper@example.test', 'points': 0}
        ).output
        self.assertIn('error', out)

    def test_scopes_declared(self):
        self.assertEqual(loyalty_balance_tool.scopes, ['crm.read'])
        self.assertEqual(loyalty_adjust_points_tool.scopes, ['crm.write'])
