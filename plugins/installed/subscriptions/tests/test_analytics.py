"""Subscription analytics — MRR / churn / trial math + dashboard boundaries."""

from __future__ import annotations

import itertools
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.subscriptions.analytics import (
    churn_rate,
    committed_mrr,
    mrr_trend,
)
from plugins.installed.subscriptions.models import Plan, Subscription, SubscriptionInvoice

User = get_user_model()

_counter = itertools.count(1)


def _customer():
    n = next(_counter)
    return User.objects.create_user(username=f'sub-c{n}', email=f'sub-c{n}@x.io', password='pw')


def _plan(price='10.00', interval='month'):
    n = next(_counter)
    return Plan.objects.create(
        name=f'Plan {n}', slug=f'plan-{n}', price=Money(Decimal(price), 'USD'), interval=interval
    )


def _sub(plan, state='active'):
    return Subscription.objects.create(customer=_customer(), plan=plan, state=state)


class MRRTests(TestCase):
    def test_committed_mrr_active_only(self):
        p = _plan('10.00', 'month')
        for _ in range(3):
            _sub(p, 'active')
        _sub(p, 'trialing')  # excluded
        _sub(p, 'cancelled')  # excluded
        self.assertEqual(committed_mrr().amount, Decimal('30.00'))

    def test_yearly_normalizes_to_monthly(self):
        _sub(_plan('10.00', 'month'), 'active')  # $10/mo
        _sub(_plan('120.00', 'year'), 'active')  # $120/yr → $10/mo
        self.assertEqual(committed_mrr().amount, Decimal('20.00'))

    def test_empty_db(self):
        self.assertEqual(committed_mrr().amount, Decimal('0.00'))

    def test_mrr_trend_recognized_from_paid_invoice(self):
        sub = _sub(_plan('10.00', 'month'), 'active')
        now = timezone.now()
        ps = now - timedelta(days=20)
        SubscriptionInvoice.objects.create(
            subscription=sub,
            period_start=ps,
            period_end=ps + timedelta(days=30),
            amount=Money(Decimal('30'), 'USD'),
            state='paid',
            paid_at=ps,
        )
        trend = mrr_trend()
        self.assertTrue(trend)
        # $30 over a 30-day period → $30 recognized that month.
        self.assertEqual(trend[-1]['mrr'], Decimal('30.00'))


class ChurnTests(TestCase):
    def test_churn_rate(self):
        p = _plan()
        now = timezone.now()
        subs = [_sub(p, 'active') for _ in range(20)]
        # All started 60 days ago (started_at is auto_now_add → set via update()).
        Subscription.objects.all().update(started_at=now - timedelta(days=60))
        for s in subs[:2]:  # cancel 2 within the 30-day window
            Subscription.objects.filter(pk=s.pk).update(
                state='cancelled', cancelled_at=now - timedelta(days=10)
            )
        c = churn_rate(days=30)
        self.assertEqual(c['active_at_start'], 20)
        self.assertEqual(c['cancelled'], 2)
        self.assertEqual(c['rate'], 10.0)


class AnalyticsPageTests(TestCase):
    URL = '/dashboard/apps/subscriptions/analytics/'

    def test_anon_blocked(self):
        self.assertIn(self.client.get(self.URL).status_code, (301, 302))

    def test_non_staff_blocked(self):
        self.client.force_login(_customer())
        self.assertIn(self.client.get(self.URL).status_code, (301, 302))

    def test_staff_ok_empty(self):
        staff = User.objects.create_user(
            username='boss-s', email='bs@x.io', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Subscription analytics')
