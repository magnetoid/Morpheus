"""Search-engine and SEO crawlers are not visitors.

Only AI crawlers were filtered (they keep their own catalog-read metric); every
other bot — Semrush, PetalBot, Applebot, Bing — became a visitor session with
pageviews and product views, and about nine in ten product-page hits on the
live stores were crawlers. Transactional events are untouched: an order placed
through an API or agent client still counts.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import Client, TestCase
from djmoney.money import Money

from core.utils.crawlers import is_crawler_user_agent
from plugins.installed.analytics.models import AnalyticsEvent, AnalyticsSession

_BROWSER = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36'
_SEMRUSH = 'Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)'


class CrawlerUserAgentTests(TestCase):
    def test_classification(self):
        for ua in (
            _SEMRUSH,
            'Mozilla/5.0 (Linux; Android 7.0;) AppleWebKit/537.36 (compatible; PetalBot)',
            'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
            'Mozilla/5.0 AppleWebKit/537.36 (compatible; GPTBot/1.2)',
            'python-requests/2.32',
            'MorpheusSiteAudit/1.0 (internal crawler)',
            '',
            None,
        ):
            with self.subTest(ua=ua):
                self.assertTrue(is_crawler_user_agent(ua))
        for ua in (
            _BROWSER,
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 '
            'Version/17.4 Mobile/15E148 Safari/604.1',
        ):
            with self.subTest(ua=ua):
                self.assertFalse(is_crawler_user_agent(ua))


class CrawlerVisitorTests(TestCase):
    def test_a_crawler_is_not_a_session_or_pageview(self):
        sessions, events = AnalyticsSession.objects.count(), AnalyticsEvent.objects.count()
        Client().get('/', HTTP_USER_AGENT=_SEMRUSH)
        self.assertEqual(AnalyticsSession.objects.count(), sessions)
        self.assertEqual(AnalyticsEvent.objects.count(), events)

    def test_a_browser_still_counts(self):
        # No consent cookie: a session-less pageview (consent gating), not a session.
        pageviews = AnalyticsEvent.objects.filter(kind='pageview').count()
        Client().get('/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(AnalyticsEvent.objects.filter(kind='pageview').count(), pageviews + 1)

    def test_a_crawler_product_view_is_not_recorded(self):
        from plugins.installed.catalog.models import Product

        Product.objects.create(
            name='Crawled',
            slug='crawled-probe',
            sku='CR-1',
            price=Money(Decimal('3.00'), 'USD'),
            status='active',
        )
        Client().get('/products/crawled-probe/', HTTP_USER_AGENT=_SEMRUSH)
        self.assertFalse(AnalyticsEvent.objects.filter(product_slug='crawled-probe').exists())

        Client().get('/products/crawled-probe/', HTTP_USER_AGENT=_BROWSER)
        self.assertTrue(AnalyticsEvent.objects.filter(product_slug='crawled-probe').exists())
