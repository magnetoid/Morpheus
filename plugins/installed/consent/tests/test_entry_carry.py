"""The banner's answer keeps where the visit came from.

Accepting cookies reloads the page, so the visit's first counted page was the
store itself: Google, a newsletter link or ChatGPT went missing from every
consented visit, and its UTMs with it (audit of 2026-11-12).
"""

from __future__ import annotations

from django.test import Client, RequestFactory, TestCase

from core.consent import ENTRY_COOKIE, entry, entry_cookie_value

_BROWSER = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Version/17.5 Safari/605.1.15'
)
_LANDING = 'http://testserver/products/lamp/?utm_source=newsletter'


class EntryCarryTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_USER_AGENT=_BROWSER)

    def _accept(self, **fields):
        return self.client.post('/consent/save/', {'accept_all': '1', **fields})

    def test_accepting_keeps_the_landing_page_and_its_referrer(self):
        response = self._accept(entry_url=_LANDING, entry_referrer='https://www.google.com/')
        cookie = response.cookies[ENTRY_COOKIE]
        request = RequestFactory().get('/')
        request.COOKIES[ENTRY_COOKIE] = cookie.value
        self.assertEqual(
            entry(request), {'referrer': 'https://www.google.com/', 'landing': _LANDING}
        )
        self.assertLessEqual(int(cookie['max-age']), 120)

    def test_a_page_after_the_first_or_another_site_carries_nothing(self):
        moved_on = self._accept(entry_url=_LANDING, entry_referrer='http://testserver/')
        self.assertNotIn(ENTRY_COOKIE, moved_on.cookies)
        elsewhere = self._accept(entry_url='https://evil.test/', entry_referrer='')
        self.assertNotIn(ENTRY_COOKIE, elsewhere.cookies)

    def test_refusing_carries_nothing(self):
        response = self.client.post('/consent/save/', {'reject_all': '1', 'entry_url': _LANDING})
        self.assertNotIn(ENTRY_COOKIE, response.cookies)

    def test_a_forged_or_stale_value_is_ignored(self):
        request = RequestFactory().get('/')
        request.COOKIES[ENTRY_COOKIE] = 'not-signed'
        self.assertIsNone(entry(request))
        request.COOKIES[ENTRY_COOKIE] = entry_cookie_value('', '')
        self.assertIsNone(entry(request))  # no landing page, nothing to say

    def test_the_banner_sends_the_page_and_its_referrer(self):
        from core.models import StoreSettings

        row = StoreSettings.objects.first() or StoreSettings()
        row.gdpr_enabled = True
        row.save()
        from django.core.cache import cache

        cache.delete('morph:gdpr_enabled')
        body = self.client.get('/').content.decode()
        self.assertIn('name="entry_referrer"', body)
        self.assertIn('name="entry_url"', body)
