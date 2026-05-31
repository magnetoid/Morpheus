"""Fraud-rules scoring tests.

Each rule's contribution to the score is verified in isolation by
constructing the minimal input that triggers exactly one rule and
asserting the score moves by the documented delta.

The buckets (ok/watch/review/reject) are tested at their boundaries
(29/30, 59/60, 79/80) so a future refactor that drifts the
thresholds breaks a test, not customer trust.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.fraud_rules.services import (
    FraudResult,
    _bucket_for,
    score_order,
)


class _FakeMoney:
    """Stand-in for djmoney Money — `total.amount` access pattern."""

    def __init__(self, amount):
        self.amount = Decimal(str(amount))


class _FakeOrder:
    """Minimal order shape that score_order reads from."""

    def __init__(
        self,
        *,
        pk='order-1',
        order_number='X-1',
        customer_id=None,
        customer_email='',
        metadata=None,
        total=Decimal('100'),
        shipping_address=None,
        billing_address=None,
    ):
        self.pk = pk
        self.order_number = order_number
        self.customer_id = customer_id
        self.customer_email = customer_email
        self.metadata = metadata or {}
        self.total = _FakeMoney(total)
        self.shipping_address = shipping_address or {}
        self.billing_address = billing_address or {}


class BucketBoundaryTests(TestCase):
    """The thresholds are the system's contract with the merchant."""

    def test_zero_is_ok(self):
        self.assertEqual(_bucket_for(0), 'ok')

    def test_below_watch_is_ok(self):
        self.assertEqual(_bucket_for(29), 'ok')

    def test_watch_starts_at_30(self):
        self.assertEqual(_bucket_for(30), 'watch')
        self.assertEqual(_bucket_for(59), 'watch')

    def test_review_starts_at_60(self):
        self.assertEqual(_bucket_for(60), 'review')
        self.assertEqual(_bucket_for(79), 'review')

    def test_reject_starts_at_80(self):
        self.assertEqual(_bucket_for(80), 'reject')
        self.assertEqual(_bucket_for(100), 'reject')


class AddressMismatchTests(TestCase):
    def test_same_country_no_flag(self):
        order = _FakeOrder(
            shipping_address={'country': 'US'},
            billing_address={'country': 'US'},
        )
        result = score_order(order)
        self.assertNotIn('address_mismatch', result.flags)

    def test_different_country_flags(self):
        order = _FakeOrder(
            shipping_address={'country': 'US'},
            billing_address={'country': 'RU'},
        )
        result = score_order(order)
        self.assertIn('address_mismatch', result.flags)
        # +15 for address mismatch, no other rules triggered → score 15 → ok bucket.
        self.assertEqual(result.score, 15)
        self.assertEqual(result.bucket, 'ok')

    def test_case_insensitive(self):
        order = _FakeOrder(
            shipping_address={'country': 'us'},
            billing_address={'country': 'US'},
        )
        result = score_order(order)
        self.assertNotIn('address_mismatch', result.flags)

    def test_empty_addresses_no_flag(self):
        order = _FakeOrder()
        result = score_order(order)
        self.assertNotIn('address_mismatch', result.flags)


class BinDenylistTests(TestCase):
    def test_no_denylist_no_flag(self):
        order = _FakeOrder(metadata={'payment_bin': '411111'})
        with patch(
            'plugins.installed.fraud_rules.services._config',
            return_value={},
        ):
            result = score_order(order)
        self.assertNotIn('bin_high_risk', result.flags)

    def test_matching_bin_flags(self):
        order = _FakeOrder(metadata={'payment_bin': '411111'})
        with patch(
            'plugins.installed.fraud_rules.services._config',
            return_value={'high_risk_bins': ['411111', '555555']},
        ):
            result = score_order(order)
        self.assertIn('bin_high_risk', result.flags)
        self.assertEqual(result.score, 25)

    def test_non_matching_bin_no_flag(self):
        order = _FakeOrder(metadata={'payment_bin': '422222'})
        with patch(
            'plugins.installed.fraud_rules.services._config',
            return_value={'high_risk_bins': ['411111']},
        ):
            result = score_order(order)
        self.assertNotIn('bin_high_risk', result.flags)


class CombinedRulesTests(TestCase):
    """When multiple rules trigger, their points sum (capped at 100)."""

    def test_address_mismatch_plus_bin(self):
        order = _FakeOrder(
            shipping_address={'country': 'US'},
            billing_address={'country': 'RU'},
            metadata={'payment_bin': '411111'},
        )
        with patch(
            'plugins.installed.fraud_rules.services._config',
            return_value={'high_risk_bins': ['411111']},
        ):
            result = score_order(order)
        # 15 + 25 = 40 → watch bucket.
        self.assertEqual(result.score, 40)
        self.assertEqual(result.bucket, 'watch')
        self.assertIn('address_mismatch', result.flags)
        self.assertIn('bin_high_risk', result.flags)

    def test_score_capped_at_100(self):
        """When points add up beyond 100, they clamp."""
        # Hand-construct: rules contributing 30+20+15+25+30 = 120 → clamp to 100.
        with (
            patch(
                'plugins.installed.fraud_rules.services._ip_velocity',
                return_value=10,
            ),
            patch(
                'plugins.installed.fraud_rules.services._email_velocity',
                return_value=10,
            ),
            patch(
                'plugins.installed.fraud_rules.services._refund_fraud_rate',
                return_value=0.7,
            ),
            patch(
                'plugins.installed.fraud_rules.services._config',
                return_value={'high_risk_bins': ['411111']},
            ),
        ):
            order = _FakeOrder(
                metadata={'payment_bin': '411111'},
                shipping_address={'country': 'US'},
                billing_address={'country': 'RU'},
            )
            result = score_order(order)
        self.assertLessEqual(result.score, 100)
        self.assertEqual(result.bucket, 'reject')


class ScoreOrderFailSafeTests(TestCase):
    """score_order MUST NOT raise — the order pipeline depends on it."""

    def test_internal_exception_returns_safe_result(self):
        order = _FakeOrder()
        # Patch one of the rule functions to raise — score_order should
        # catch it and return FraudResult(score=0, flags=['score_failed']).
        with patch(
            'plugins.installed.fraud_rules.services._ip_velocity',
            side_effect=RuntimeError('boom'),
        ):
            result = score_order(order)
        self.assertIsInstance(result, FraudResult)
        self.assertEqual(result.score, 0)
        self.assertEqual(result.bucket, 'ok')
        self.assertIn('score_failed', result.flags)


class NewCustomerHighValueTests(TestCase):
    """First-order + high-value rule (+10)."""

    def _run_with_safe_db_rules(self, order):
        """Patch every rule that touches the real ORM so only the
        first-order + high-value rule remains. Lets us test that one
        rule in isolation without an Order/StockLevel fixture."""
        patches = [
            patch('plugins.installed.fraud_rules.services._ip_velocity', return_value=0),
            patch('plugins.installed.fraud_rules.services._email_velocity', return_value=0),
            patch('plugins.installed.fraud_rules.services._refund_fraud_rate', return_value=0.0),
        ]
        for p in patches:
            p.start()
        try:
            return score_order(order)
        finally:
            for p in patches:
                p.stop()

    def test_new_customer_high_value_flags(self):
        User = get_user_model()
        cust = User.objects.create_user(username='alice', email='a@x.test', password='x')
        order = _FakeOrder(
            pk='ord-new',
            customer_id=cust.pk,
            customer_email='a@x.test',
            total=Decimal('1000'),
        )
        with patch(
            'plugins.installed.fraud_rules.services._is_first_order',
            return_value=True,
        ):
            result = self._run_with_safe_db_rules(order)
        self.assertIn('new_high_value', result.flags)
        self.assertGreaterEqual(result.score, 10)

    def test_low_value_first_order_no_flag(self):
        User = get_user_model()
        cust = User.objects.create_user(username='bob', email='b@x.test', password='x')
        order = _FakeOrder(
            customer_id=cust.pk,
            customer_email='b@x.test',
            total=Decimal('50'),
        )
        with patch(
            'plugins.installed.fraud_rules.services._is_first_order',
            return_value=True,
        ):
            result = self._run_with_safe_db_rules(order)
        self.assertNotIn('new_high_value', result.flags)
