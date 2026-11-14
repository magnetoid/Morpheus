"""One attribution page: spend from the Channels app, in the store currency."""

from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.admin_dashboard import navigation
from plugins.installed.analytics.models import AdSpendSnapshot, AnalyticsEvent, AnalyticsSession
from plugins.installed.analytics.services_attribution import attribute_revenue, collect_ad_spend
from plugins.installed.channels.tasks import METRICS_CACHE_KEY
from plugins.registry import app_registry

User = get_user_model()
URL = '/dashboard/apps/analytics/attribution/'


def _cell(html: str, channel: str, col: str) -> str:
    row = re.search(rf'<tr data-channel="{channel}">(.*?)</tr>', html, re.S).group(1)
    return re.search(rf'data-col="{col}">(.*?)</td>', row, re.S).group(1).strip()


@override_settings(STORE_CURRENCY='EUR')
class AttributionPageTests(TestCase):
    def setUp(self):
        self.addCleanup(cache.delete, METRICS_CACHE_KEY)
        cache.set(
            METRICS_CACHE_KEY,
            [{'name': 'google_shopping', 'spend': 120, 'revenue': 300, 'conversions': 4}],
            600,
        )
        self.staff = User.objects.create_user(
            username='attrstaff', email='as@x.io', password='pw', is_staff=True, is_superuser=True
        )
        self.client.force_login(self.staff)
        # A: one Google visit, buys 100. B: Google then Facebook, buys 60.
        # C: no visits (direct), buys 40.
        a, b, c = (
            User.objects.create_user(username=n, email=f'{n}@x.io', password='pw') for n in 'abc'
        )
        self._visit(a, 'googleads', days_ago=3)
        self._visit(b, 'googleads', days_ago=5)
        self._visit(b, 'facebook', days_ago=1)
        for who, amount in ((a, 100), (b, 60), (c, 40)):
            AnalyticsEvent.objects.create(
                name='order.placed',
                kind='purchase',
                customer=who,
                revenue=Money(Decimal(amount), 'EUR'),
            )

    def _visit(self, user, source, days_ago):
        s = AnalyticsSession.objects.create(
            cookie_id=f'{user.pk}-{source}', customer=user, utm_source=source
        )
        AnalyticsSession.objects.filter(pk=s.pk).update(
            first_seen_at=timezone.now() - timedelta(days=days_ago)
        )

    def _run_jobs(self):
        self.assertEqual(collect_ad_spend(), 1)
        attribute_revenue()

    def test_page_shows_spend_platform_claim_and_model_revenue_in_store_currency(self):
        self._run_jobs()
        html = self.client.get(URL).content.decode()
        self.assertIn('€120.00', _cell(html, 'google', 'spend'))
        self.assertIn('€300.00', _cell(html, 'google', 'platform-revenue'))
        self.assertEqual(_cell(html, 'google', 'conversions'), '4')
        # Last touch: A's 100 (B's last visit was Facebook).
        self.assertIn('€100.00', _cell(html, 'google', 'revenue'))
        # Blended MER: all store revenue (200) over total spend (120).
        mer = re.search(r'data-kpi="mer">(.*?)</p>', html, re.S).group(1).strip()
        self.assertEqual(mer, '1.67×')

    def test_model_changes_the_attributed_column(self):
        self._run_jobs()
        html = self.client.get(URL + '?model=linear').content.decode()
        self.assertIn('€130.00', _cell(html, 'google', 'revenue'))  # 100 + half of B's 60

    def test_spend_is_stored_in_the_store_currency(self):
        from plugins.installed.analytics.models import DailyMetric

        self._run_jobs()
        self.assertEqual(str(AdSpendSnapshot.objects.get(channel='google').spend.currency), 'EUR')
        for m in DailyMetric.objects.filter(metric='attribution'):
            self.assertEqual(str(m.value_money.currency), 'EUR')

    def test_channels_off_still_renders_revenue_and_says_where_spend_comes_from(self):
        attribute_revenue()
        app_registry.deactivate('channels')
        self.addCleanup(app_registry.activate, 'channels')
        self.assertEqual(collect_ad_spend(), 0)
        self.assertFalse(AdSpendSnapshot.objects.exists())
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('€100.00', _cell(html, 'google', 'revenue'))
        self.assertEqual(_cell(html, 'google', 'spend'), '—')
        mer = re.search(r'data-kpi="mer">(.*?)</p>', html, re.S).group(1).strip()
        self.assertEqual(mer, '—')
        self.assertIn('data-note="spend-from-channels"', html)

    def test_empty_cache_renders_without_spend(self):
        cache.delete(METRICS_CACHE_KEY)
        self.assertEqual(collect_ad_spend(), 0)
        attribute_revenue()
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-note="spend-from-channels"')


class RoasPageIsGoneTests(TestCase):
    def test_roas_page_is_gone(self):
        staff = User.objects.create_user(
            username='gone', email='g@x.io', password='pw', is_staff=True, is_superuser=True
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/dashboard/apps/channels/attribution/').status_code, 404)
        labels = [t.label for t in navigation.tabs(staff) if t.section == 'channels']
        self.assertNotIn('ROAS', labels)


class RevenueBySourceTests(TestCase):
    def _purchase(self, source, amount):
        import uuid

        sess = AnalyticsSession.objects.create(cookie_id=uuid.uuid4().hex, utm_source=source)
        AnalyticsEvent.objects.create(
            name='order.placed',
            kind='purchase',
            session=sess,
            revenue=Money(Decimal(str(amount)), 'USD'),
        )

    def test_revenue_by_source(self):
        from plugins.installed.analytics.services import revenue_by_source

        self._purchase('google', 100)
        self._purchase('tiktok', 40)
        self._purchase('', 60)  # direct / untagged
        rev = revenue_by_source(days=30)
        self.assertEqual(rev['total'], 200.0)
        self.assertEqual(rev['by_source'].get('google'), 100.0)
        self.assertEqual(rev['direct'], 60.0)

    def test_a_non_numeric_platform_revenue_renders_blank_not_500(self):
        from plugins.installed.analytics.services_attribution import roas_by_channel

        AdSpendSnapshot.objects.create(
            day=timezone.now().date(),
            channel='google',
            spend=Money(Decimal('10'), 'USD'),
            source_meta={'platform_revenue': 'n/a', 'conversions': 3.5},
        )
        [row] = roas_by_channel(model='last_touch')
        self.assertIsNone(row['platform_revenue'])
        self.assertEqual(row['conversions'], 3.5)
