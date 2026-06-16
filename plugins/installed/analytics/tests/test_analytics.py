"""Analytics tests."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone
from djmoney.money import Money

from core.agents import agent_registry
from plugins.installed.analytics.models import (
    AnalyticsEvent,
    DailyMetric,
)
from plugins.installed.analytics.services import (
    funnel_for,
    get_or_create_session,
    record_event,
    roll_daily,
    should_track_customer,
    should_track_request,
    trim_old_events,
)

User = get_user_model()


def _set_analytics_config(**kwargs):
    from plugins.registry import plugin_registry

    p = None
    for attr in ('get', 'get_plugin'):
        fn = getattr(plugin_registry, attr, None)
        if callable(fn):
            try:
                p = fn('analytics')
            except Exception:  # noqa: BLE001
                p = None
            if p is not None:
                break
    if p is None:
        from plugins.installed.analytics.plugin import AnalyticsPlugin

        p = AnalyticsPlugin()
    for k, v in kwargs.items():
        p.set_config(k, v)
    p.invalidate_config_cache()


class SessionTests(TestCase):
    def test_creates_session_with_cookie(self):
        rf = RequestFactory()
        req = rf.get('/?utm_source=newsletter')
        sess = get_or_create_session(req)
        self.assertIsNotNone(sess)
        self.assertEqual(sess.utm_source, 'newsletter')
        self.assertEqual(sess.event_count, 0)

    def test_links_customer_after_login(self):
        rf = RequestFactory()
        cust = User.objects.create_user(username='u', email='u@example.com', password='x')
        req = rf.get('/')
        req.user = cust
        sess = get_or_create_session(req)
        sess.refresh_from_db()
        self.assertEqual(sess.customer_id, cust.id)


class RecordEventTests(TestCase):
    def test_record_event_writes_row_and_bumps_session(self):
        rf = RequestFactory()
        req = rf.get('/')
        sess = get_or_create_session(req)
        evt = record_event(
            name='product.viewed', kind='product_view', session=sess, product_slug='the-quiet-hour'
        )
        self.assertIsNotNone(evt)
        sess.refresh_from_db()
        self.assertEqual(sess.event_count, 1)
        self.assertEqual(AnalyticsEvent.objects.count(), 1)


class RollupTests(TestCase):
    def setUp(self):
        rf = RequestFactory()
        self.req = rf.get('/')
        self.sess = get_or_create_session(self.req)

    def test_roll_daily_writes_metrics(self):
        # Create events dated yesterday so the rollup picks them up.
        yesterday = timezone.now().date() - timedelta(days=1)
        ts = timezone.now() - timedelta(days=1)
        # bypass auto_now_add by writing directly:
        AnalyticsEvent.objects.create(
            name='pageview',
            kind='pageview',
            session=self.sess,
            url='/',
        )
        AnalyticsEvent.objects.filter(name='pageview').update(created_at=ts)
        AnalyticsEvent.objects.create(
            name='order.placed',
            kind='purchase',
            session=self.sess,
            revenue=Money(Decimal('25'), 'USD'),
        )
        AnalyticsEvent.objects.filter(name='order.placed').update(created_at=ts)

        n = roll_daily(day=yesterday)
        self.assertGreater(n, 0)
        self.assertEqual(
            DailyMetric.objects.filter(metric='pageviews', day=yesterday).first().value_int, 1
        )
        self.assertEqual(
            DailyMetric.objects.filter(metric='orders', day=yesterday).first().value_int, 1
        )
        rev = DailyMetric.objects.filter(metric='revenue', day=yesterday).first()
        self.assertIsNotNone(rev)
        self.assertEqual(rev.value_money.amount, Decimal('25'))


class FunnelTests(TestCase):
    def test_funnel_walks_steps(self):
        rf = RequestFactory()
        s1 = get_or_create_session(rf.get('/'))
        # Force unique cookie for second session
        req2 = rf.get('/')
        req2.COOKIES = {'morph_aid': 'cookie2'}
        s2 = get_or_create_session(req2)
        # s1 hits all three; s2 only hits two
        record_event(name='pageview', kind='pageview', session=s1)
        record_event(name='product.viewed', kind='product_view', session=s1, product_slug='a')
        record_event(name='cart.add', kind='cart', session=s1)
        record_event(name='pageview', kind='pageview', session=s2)
        record_event(name='product.viewed', kind='product_view', session=s2, product_slug='b')

        rows = funnel_for(steps=['pageview', 'product.viewed', 'cart.add'], days=30)
        self.assertEqual(rows[0]['sessions'], 2)
        self.assertEqual(rows[1]['sessions'], 2)
        self.assertEqual(rows[2]['sessions'], 1)


class AgentToolTests(TestCase):
    def test_tools_registered(self):
        names = {t.name for t in agent_registry.platform_tools()}
        for required in (
            'analytics.summary',
            'analytics.funnel',
            'analytics.realtime',
            'analytics.search_trends',
            'analytics.agent_costs',
            'analytics.top_products',
        ):
            self.assertIn(required, names)


class TrimTests(TestCase):
    def test_trim_old_events(self):
        rf = RequestFactory()
        sess = get_or_create_session(rf.get('/'))
        AnalyticsEvent.objects.create(name='old', kind='pageview', session=sess)
        AnalyticsEvent.objects.filter(name='old').update(
            created_at=timezone.now() - timedelta(days=200)
        )
        AnalyticsEvent.objects.create(name='new', kind='pageview', session=sess)
        deleted = trim_old_events(keep_days=90)
        self.assertEqual(deleted, 1)
        self.assertTrue(AnalyticsEvent.objects.filter(name='new').exists())


class StaffExclusionTests(TestCase):
    """Staff/admins are excluded from tracking; everyone else is tracked."""

    def setUp(self):
        self.rf = RequestFactory()

    def test_anonymous_is_tracked(self):
        from django.contrib.auth.models import AnonymousUser

        req = self.rf.get('/')
        req.user = AnonymousUser()
        self.assertTrue(should_track_request(req))

    def test_customer_is_tracked(self):
        req = self.rf.get('/')
        req.user = User.objects.create_user(username='c', email='c@example.com', password='x')
        self.assertTrue(should_track_request(req))

    def test_staff_is_excluded(self):
        req = self.rf.get('/')
        req.user = User.objects.create_user(
            username='s', email='s@example.com', password='x', is_staff=True
        )
        self.assertFalse(should_track_request(req))

    def test_superuser_is_excluded(self):
        req = self.rf.get('/')
        req.user = User.objects.create_superuser(username='a', email='a@example.com', password='x')
        self.assertFalse(should_track_request(req))

    def test_beacon_skips_staff(self):
        from django.test import Client

        c = Client()
        c.force_login(
            User.objects.create_user(
                username='s2', email='s2@example.com', password='x', is_staff=True
            )
        )
        r = c.post(
            '/api/analytics/track/',
            data={'name': 'pageview', 'kind': 'pageview'},
        )
        self.assertEqual(r.status_code, 204)
        self.assertEqual(AnalyticsEvent.objects.count(), 0)

    def test_exclude_staff_toggle_off_tracks_staff(self):
        _set_analytics_config(exclude_staff=False)
        self.addCleanup(_set_analytics_config, exclude_staff=True, exclude_logged_in=False)
        req = self.rf.get('/')
        req.user = User.objects.create_user(
            username='s3', email='s3@example.com', password='x', is_staff=True
        )
        self.assertTrue(should_track_request(req))

    def test_exclude_logged_in_toggle_excludes_customer(self):
        _set_analytics_config(exclude_logged_in=True)
        self.addCleanup(_set_analytics_config, exclude_staff=True, exclude_logged_in=False)
        req = self.rf.get('/')
        req.user = User.objects.create_user(username='c2', email='c2@example.com', password='x')
        self.assertFalse(should_track_request(req))

    def test_hook_path_excludes_staff_customer(self):
        """A staff member's order/product events (no HttpRequest) are excluded."""
        staff = User.objects.create_user(
            username='s4', email='s4@example.com', password='x', is_staff=True
        )
        self.assertFalse(should_track_customer(staff))
        record_event(name='order.placed', kind='order', customer=staff)
        self.assertEqual(AnalyticsEvent.objects.count(), 0)
        # A regular customer's event is still recorded.
        cust = User.objects.create_user(username='c3', email='c3@example.com', password='x')
        record_event(name='order.placed', kind='order', customer=cust)
        self.assertEqual(AnalyticsEvent.objects.count(), 1)
