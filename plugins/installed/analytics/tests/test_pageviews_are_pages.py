"""A pageview is a page: a script's JSON fetch is not one.

The travel store's search bar asks /bookings/suggest/ for suggestions as a visitor
types, and every storefront GET was recorded as a pageview whatever it returned; the
cookie banner's /csrf/ fetch already was.
"""

from __future__ import annotations

from django.test import Client, TestCase

from plugins.installed.analytics.models import AnalyticsEvent

_GPTBOT = 'Mozilla/5.0 AppleWebKit/537.36 (compatible; GPTBot/1.2; +https://openai.com/gptbot)'
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

    def test_a_form_post_or_a_head_request_is_not_a_pageview(self):
        # A POST that redirects answers text/html too; only a GET is a page someone saw.
        before = self._pageviews()
        client = Client(HTTP_USER_AGENT=_BROWSER)
        response = client.post('/i18n/setlang/', {'language': 'en', 'next': '/'})
        self.assertEqual(response.status_code, 302)
        client.head('/')
        self.assertEqual(self._pageviews(), before)

    def test_an_ai_crawler_reading_a_text_file_still_counts(self):
        # robots.txt, llms.txt and the feeds are what AI crawlers read most.
        from plugins.installed.analytics.models import DailyMetric

        Client().get('/robots.txt', HTTP_USER_AGENT=_GPTBOT)
        row = DailyMetric.objects.get(metric='ai_crawler_hits', dimension='gptbot')
        self.assertEqual(row.value_int, 1)
