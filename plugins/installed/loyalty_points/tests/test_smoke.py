"""Loyalty smoke test — award_points stores a row, get_balance sums it,
and the ORDER_PAID hook fires the earn handler."""

# ruff: noqa: PLC0415, I001
# Inline imports are intentional in tests — avoid touching the app
# registry at module-import time.
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase


class LoyaltySmoke(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='buyer@example.com',
            email='buyer@example.com',
            password='hunter2',
        )

    def test_award_and_balance(self):
        from plugins.installed.loyalty_points import services

        services.award_points(self.user, 25, reason='earn_order', order_number='X-1', note='test')
        self.assertEqual(services.get_balance(self.user), 25)
        # Idempotent on (customer, order_number) for earn_order.
        services.award_points(self.user, 25, reason='earn_order', order_number='X-1', note='test')
        self.assertEqual(services.get_balance(self.user), 25)

    def test_order_paid_hook_registered(self):
        from core.hooks import hook_registry, MorpheusEvents

        handlers = hook_registry._handlers.get(MorpheusEvents.ORDER_PAID, [])
        names = [h.__qualname__ for _, h in handlers]
        self.assertIn('_on_order_paid', names)
