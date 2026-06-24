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
        # Entries are (priority, handler, mode) tuples; handler is index 1.
        names = [entry[1].__qualname__ for entry in handlers]
        self.assertIn('_on_order_paid', names)


class LoyaltyGuestGuard(TestCase):
    """The ORDER_PAID handler must award points only to authenticated customers,
    never to a guest customer object that lacks ``is_authenticated`` (regression:
    the guard previously defaulted that attribute to True)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='buyer2@example.com',
            email='buyer2@example.com',
            password='hunter2',
        )

    def _order(self, customer, *, total=25, number='G-1'):
        from types import SimpleNamespace

        return SimpleNamespace(customer=customer, user=None, total=total, number=number, pk=1)

    def test_authenticated_customer_earns(self):
        from plugins.installed.loyalty_points import services

        services._on_order_paid(order=self._order(self.user))
        self.assertEqual(services.get_balance(self.user), 25)

    def test_guest_without_is_authenticated_earns_nothing(self):
        from unittest import mock

        from plugins.installed.loyalty_points import services

        guest = object()  # no is_authenticated attribute → must be skipped
        with mock.patch.object(services, 'award_points') as award:
            services._on_order_paid(order=self._order(guest))
            award.assert_not_called()
