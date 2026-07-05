"""Funnel drop-off — regression for the KeyError('name') 500 (step_dropoffs
read prev['name'] but funnel_for returns {'step', 'sessions'})."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.analytics.models import AnalyticsSession
from plugins.installed.analytics.services import record_event
from plugins.installed.analytics.services_cohorts import step_dropoffs


def _session(n: str) -> AnalyticsSession:
    return AnalyticsSession.objects.create(cookie_id=f'ck-{n}')


def _seed_two_step_funnel():
    """3 sessions hit step one, 1 continues to step two."""
    for i in range(3):
        s = _session(str(i))
        record_event(name='pageview', kind='pageview', session=s)
    survivor = AnalyticsSession.objects.first()
    record_event(name='product.viewed', kind='product_view', session=survivor)


class StepDropoffsTests(TestCase):
    def test_two_steps_no_keyerror_and_correct_keys(self):
        _seed_two_step_funnel()
        rows = step_dropoffs(steps=['pageview', 'product.viewed'], days=30)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['from_step'], 'pageview')
        self.assertEqual(rows[0]['to_step'], 'product.viewed')
        self.assertEqual(rows[0]['prev_count'], 3)
        self.assertEqual(rows[0]['cur_count'], 1)


class FunnelViewTests(TestCase):
    def test_funnel_page_renders_200_with_data(self):
        _seed_two_step_funnel()
        staff = get_user_model().objects.create_user(
            username='staff', email='staff@test.local', password='x', is_staff=True
        )
        self.client.force_login(staff)
        resp = self.client.get(
            '/dashboard/analytics/v2/funnel/',
            {'steps': 'pageview,product.viewed'},
        )
        self.assertEqual(resp.status_code, 200)
