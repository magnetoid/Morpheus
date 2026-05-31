"""Referral lifecycle tests.

Verifies the three-state machine (pending → qualified → rewarded)
and the points minting math.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.loyalty_points.models import PointsTransaction, Referral
from plugins.installed.loyalty_points.services_referrals import (
    DEFAULT_REFEREE_REWARD,
    DEFAULT_REFERRER_REWARD,
    MIN_QUALIFYING_ORDER_USD,
    qualify_on_order,
    record_referral,
    referral_code_for,
)


class _FakeMoney:
    def __init__(self, amount):
        self.amount = Decimal(str(amount))


class _FakeOrder:
    def __init__(self, *, customer_id, total, order_number='X-1'):
        self.customer_id = customer_id
        self.total = _FakeMoney(total)
        self.order_number = order_number


class ReferralCodeTests(TestCase):
    def test_first_call_mints_persistent_code(self):
        User = get_user_model()
        u = User.objects.create_user(
            username='alice',
            email='a@x.test',
            password='x',
        )
        # `metadata` is a plain dict on User in this test setup —
        # services_referrals.referral_code_for writes via setattr +
        # save(update_fields=['metadata']); when metadata isn't a real
        # field on the User model we expect save() to log + swallow.
        u.metadata = {}
        u.save = lambda update_fields=None: None  # noqa: ARG005 — stub
        code1 = referral_code_for(u)
        self.assertTrue(code1)
        self.assertGreaterEqual(len(code1), 6)

    def test_existing_code_is_returned_unchanged(self):
        User = get_user_model()
        u = User.objects.create_user(
            username='bob',
            email='b@x.test',
            password='x',
        )
        u.metadata = {'referral_code': 'FIXED123'}
        u.save = lambda update_fields=None: None  # noqa: ARG005
        self.assertEqual(referral_code_for(u), 'FIXED123')


class RecordReferralTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.referrer = User.objects.create_user(
            username='ref',
            email='ref@x.test',
            password='x',
        )
        self.referrer.metadata = {'referral_code': 'REF1'}
        self.referrer.save(update_fields=[])

        self.referee = User.objects.create_user(
            username='new',
            email='new@x.test',
            password='x',
        )

    def test_invalid_code_no_op(self):
        record_referral(referrer_code='BAD-CODE', referee=self.referee)
        self.assertEqual(Referral.objects.count(), 0)

    def test_empty_code_no_op(self):
        record_referral(referrer_code='', referee=self.referee)
        self.assertEqual(Referral.objects.count(), 0)

    def test_self_referral_blocked(self):
        record_referral(referrer_code='REF1', referee=self.referrer)
        self.assertEqual(Referral.objects.count(), 0)


class QualifyOnOrderTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.referrer = User.objects.create_user(
            username='referrer',
            email='r@x.test',
            password='x',
        )
        self.referee = User.objects.create_user(
            username='referee',
            email='e@x.test',
            password='x',
        )
        self.referral = Referral.objects.create(
            referrer=self.referrer,
            referee=self.referee,
            code='REF1',
            status='pending',
        )

    def test_below_threshold_does_not_qualify(self):
        order = _FakeOrder(
            customer_id=self.referee.pk,
            total=MIN_QUALIFYING_ORDER_USD - Decimal('1'),
        )
        qualify_on_order(order)
        self.referral.refresh_from_db()
        self.assertEqual(self.referral.status, 'pending')
        self.assertEqual(PointsTransaction.objects.count(), 0)

    def test_above_threshold_qualifies_and_mints_both_rewards(self):
        order = _FakeOrder(
            customer_id=self.referee.pk,
            total=MIN_QUALIFYING_ORDER_USD + Decimal('10'),
            order_number='Q-001',
        )
        qualify_on_order(order)

        self.referral.refresh_from_db()
        self.assertEqual(self.referral.status, 'rewarded')
        self.assertEqual(self.referral.qualifying_order_number, 'Q-001')
        self.assertIsNotNone(self.referral.qualified_at)
        self.assertIsNotNone(self.referral.rewarded_at)
        self.assertEqual(self.referral.referrer_reward_points, DEFAULT_REFERRER_REWARD)
        self.assertEqual(self.referral.referee_reward_points, DEFAULT_REFEREE_REWARD)

        # Two PointsTransaction rows — one each side.
        referrer_tx = PointsTransaction.objects.get(customer=self.referrer)
        referee_tx = PointsTransaction.objects.get(customer=self.referee)
        self.assertEqual(referrer_tx.points, DEFAULT_REFERRER_REWARD)
        self.assertEqual(referee_tx.points, DEFAULT_REFEREE_REWARD)
        self.assertEqual(referrer_tx.reason, 'adjust')

    def test_already_rewarded_referral_no_double_mint(self):
        self.referral.status = 'rewarded'
        self.referral.save(update_fields=['status'])
        order = _FakeOrder(
            customer_id=self.referee.pk,
            total=MIN_QUALIFYING_ORDER_USD + Decimal('100'),
        )
        qualify_on_order(order)
        self.assertEqual(PointsTransaction.objects.count(), 0)

    def test_no_pending_referral_no_op(self):
        Referral.objects.all().delete()
        order = _FakeOrder(
            customer_id=self.referee.pk,
            total=MIN_QUALIFYING_ORDER_USD + Decimal('50'),
        )
        qualify_on_order(order)
        self.assertEqual(PointsTransaction.objects.count(), 0)

    def test_missing_customer_id_no_op(self):
        order = _FakeOrder(
            customer_id=None,
            total=MIN_QUALIFYING_ORDER_USD + Decimal('50'),
        )
        qualify_on_order(order)
        self.referral.refresh_from_db()
        self.assertEqual(self.referral.status, 'pending')
