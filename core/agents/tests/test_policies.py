"""Scope + budget policy guards (`core/agents/policies.py`).

`enforce_budget` exists but is not yet wired into the runtime loop (Phase 4
will call it) — lock its behavior now so that wiring is safe.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from core.agents.policies import (
    BudgetExceeded,
    ScopeDenied,
    enforce_budget,
    enforce_policy,
)


class EnforcePolicyTests(SimpleTestCase):
    def test_superset_passes(self):
        enforce_policy(scopes=['catalog.read', 'catalog.write'], required=['catalog.read'])

    def test_empty_required_passes(self):
        enforce_policy(scopes=[], required=[])

    def test_missing_scope_denied(self):
        with self.assertRaises(ScopeDenied) as ctx:
            enforce_policy(scopes=['catalog.read'], required=['catalog.read', 'orders.write'])
        self.assertIn('orders.write', str(ctx.exception))


class EnforceBudgetTests(SimpleTestCase):
    def test_none_cap_is_noop(self):
        enforce_budget(spent=10_000, cap=None)

    def test_under_cap_passes(self):
        enforce_budget(spent=Decimal('1.50'), cap=Decimal('2.00'))
        enforce_budget(spent=2, cap=2)  # equal is allowed

    def test_over_cap_raises(self):
        with self.assertRaises(BudgetExceeded):
            enforce_budget(spent=Decimal('2.01'), cap=Decimal('2.00'))

    def test_invalid_values_raise_budget_exceeded(self):
        with self.assertRaises(BudgetExceeded):
            enforce_budget(spent='not-a-number', cap=1)
