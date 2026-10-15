"""A pageview is a page: a script's JSON fetch is not one.

The travel store's search bar asks /bookings/suggest/ for suggestions as a visitor
types, and every storefront GET was recorded as a pageview whatever it returned; the
cookie banner's /csrf/ fetch already was.
"""

from __future__ import annotations

from django.test import Client, TestCase

from plugins.installed.analytics.models import AnalyticsEvent

_BROWSER = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Version/17.5 Safari/605.1.15'
)


class PageviewsArePagesTests(TestCase):
    def _pageviews(self):
        return AnalyticsEvent.objects.filter(kind='pageview').count()

    def test_a_json_fetch_is_not_a_pageview(self):
        before = self._pageviews()
        response = Client(HTTP_USER_AGENT=_BROWSER).get('/csrf/')
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        self.assertEqual(self._pageviews(), before)

    def test_a_page_still_is(self):
        before = self._pageviews()
        Client(HTTP_USER_AGENT=_BROWSER).get('/')
        self.assertEqual(self._pageviews(), before + 1)
