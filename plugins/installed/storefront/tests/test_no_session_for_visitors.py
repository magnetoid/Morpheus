"""A visitor's GET writes no session and sets no session cookie.

ai_assistant's middleware wrote `session['ab_cohort']`, which nothing read, on
every request: with database sessions that was an INSERT plus `Set-Cookie:
sessionid` per crawler hit, and the cookie took the visitor's later pages out
of the edge cache (`sessionid` is a private cookie in storefront/middleware.py).
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product

_BROWSER = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15'
_CRAWLER = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'


class NoSessionForVisitorsTests(TestCase):
    def setUp(self):
        Product.objects.create(
            name='Visit',
            slug='visit-probe',
            sku='VIS',
            price=Money(Decimal('3'), 'USD'),
            product_type='simple',
            status='active',
        )

    def test_the_home_page_sets_no_session_cookie(self):
        resp = self.client.get('/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(settings.SESSION_COOKIE_NAME, resp.cookies)
        self.assertEqual(Session.objects.count(), 0)

    def test_a_crawler_on_a_product_page_gets_no_session(self):
        # Review Focus 5. dynamics and advanced_ecommerce kept a recently-viewed
        # list for every product hit, crawlers included (~9 in 10 hits).
        resp = self.client.get('/products/visit-probe/', HTTP_USER_AGENT=_CRAWLER)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(settings.SESSION_COOKIE_NAME, resp.cookies)
        self.assertEqual(Session.objects.count(), 0)

    def test_a_shopper_still_gets_a_recently_viewed_list(self):
        self.client.get('/products/visit-probe/', HTTP_USER_AGENT=_BROWSER)
        self.assertEqual(self.client.session.get('recently_viewed'), ['visit-probe'])

    def test_the_environments_middleware_is_not_in_the_stack(self):
        self.assertNotIn(
            'plugins.installed.environments.middleware.EnvironmentMiddleware',
            settings.MIDDLEWARE,
        )
