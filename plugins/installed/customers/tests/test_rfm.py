"""RFM segmentation — classify() cases + recompute (creates, flips, hook, migration)."""

from __future__ import annotations

import itertools
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.hooks import MorpheusEvents
from plugins.installed.customers.models import CustomerSegment, SegmentMigration
from plugins.installed.customers.rfm import classify, recompute_all

User = get_user_model()
_c = itertools.count(1)


def _cust(days_ago, purchases, ltv):
    n = next(_c)
    u = User.objects.create_user(username=f'rfm{n}', email=f'rfm{n}@x.io', password='pw')
    u.last_order_at = timezone.now() - timedelta(days=days_ago)
    u.purchase_count = purchases
    u.lifetime_value = Decimal(ltv)
    u.save(update_fields=['last_order_at', 'purchase_count', 'lifetime_value'])
    return u


class ClassifyTests(TestCase):
    def test_segments(self):
        self.assertEqual(classify(5, 5, 5, 100, False), 'champions')
        self.assertEqual(classify(1, 1, 1, 100, False), 'lost')
        self.assertEqual(classify(1, 4, 3, 100, False), 'at_risk')  # low R, high F
        self.assertEqual(classify(4, 2, 3, 100, False), 'potential')  # good R, low F
        self.assertEqual(classify(3, 4, 2, 100, False), 'loyal')
        self.assertEqual(classify(2, 1, 1, 1, True), 'new')  # single recent order


class RecomputeTests(TestCase):
    def _seed(self):
        # c1 highest on every dimension → champion; strictly descending after.
        self.c1 = _cust(1, 100, 10000)
        _cust(10, 50, 5000)
        _cust(20, 20, 2000)
        _cust(40, 10, 1000)
        _cust(100, 5, 500)
        _cust(300, 1, 100)

    def test_creates_segments(self):
        self._seed()
        result = recompute_all()
        self.assertEqual(result['total'], 6)
        self.assertTrue(
            CustomerSegment.objects.filter(customer=self.c1, segment='champions').exists()
        )

    def test_flip_fires_hook_and_logs_migration(self):
        self._seed()
        recompute_all()
        self.assertEqual(CustomerSegment.objects.get(customer=self.c1).segment, 'champions')
        # Crash c1 to the bottom of every dimension.
        self.c1.purchase_count = 1
        self.c1.lifetime_value = Decimal('50')
        self.c1.last_order_at = timezone.now() - timedelta(days=400)
        self.c1.save(update_fields=['purchase_count', 'lifetime_value', 'last_order_at'])
        with patch('core.hooks.hook_registry.fire') as mock_fire:
            recompute_all()
        self.assertNotEqual(CustomerSegment.objects.get(customer=self.c1).segment, 'champions')
        self.assertTrue(
            SegmentMigration.objects.filter(customer=self.c1, old_segment='champions').exists()
        )
        fired = [c.args[0] for c in mock_fire.call_args_list if c.args]
        self.assertIn(MorpheusEvents.CUSTOMER_SEGMENT_CHANGED, fired)
        # Contract (core/hooks.py): customer=<Customer>, not a bare pk. The
        # win-back subscriber dereferences customer.email, so passing customer_id
        # silently no-op'd every subscriber (the bug this now guards). Crashing c1
        # reshuffles quintiles so several customers flip — assert the contract on
        # every fire, and that c1's flip is among them.
        seg_calls = [
            c
            for c in mock_fire.call_args_list
            if c.args and c.args[0] == MorpheusEvents.CUSTOMER_SEGMENT_CHANGED
        ]
        self.assertTrue(seg_calls)
        for c in seg_calls:
            self.assertIn('customer', c.kwargs)  # object, not customer_id
            self.assertNotIn('customer_id', c.kwargs)
            self.assertTrue(hasattr(c.kwargs['customer'], 'email'))
        self.assertIn(self.c1.pk, [c.kwargs['customer'].pk for c in seg_calls])


class SegmentsPageTests(TestCase):
    URL = '/dashboard/apps/customers/segments/'

    def test_anon_blocked(self):
        self.assertIn(self.client.get(self.URL).status_code, (301, 302))

    def test_non_staff_blocked(self):
        u = User.objects.create_user(username='plain', email='p@x.io', password='pw')
        self.client.force_login(u)
        self.assertIn(self.client.get(self.URL).status_code, (301, 302))

    def test_staff_ok(self):
        staff = User.objects.create_user(
            username='bossrfm', email='br@x.io', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Customer segments')
