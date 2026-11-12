"""GA4 hears the page a consented visit landed on, and its referrer.

After "Accept" the page reloads and GA4's first hit named the store as the
referrer and the reloaded address as the landing page (audit of 2026-11-12).
"""

from __future__ import annotations

from django.core.cache import cache
from django.template import Context, Template
from django.test import RequestFactory, TestCase

from core.consent import ENTRY_COOKIE, entry_cookie_value
from plugins.installed.tracking.models import TrackingSettings

_HEAD = Template('{% load tracking %}{% tracking_head %}')
_LANDING = 'https://testserver/products/lamp/?utm_source=newsletter'


class EntryReferrerTests(TestCase):
    def setUp(self):
        from core.models import StoreSettings

        row = StoreSettings.objects.first() or StoreSettings()
        row.gdpr_enabled = False
        row.save()
        cache.delete('morph:gdpr_enabled')

    def _render(self, carried=True, **fields):
        s = TrackingSettings.get_solo()
        for key, value in fields.items():
            setattr(s, key, value)
        s.save()
        request = RequestFactory().get('/products/lamp/', HTTP_HOST='testserver')
        if carried:
            request.COOKIES[ENTRY_COOKIE] = entry_cookie_value('https://www.google.com/', _LANDING)
        return _HEAD.render(Context({'request': request}))

    def test_ga4_gets_the_landing_page_and_referrer_once(self):
        html = self._render(measurement_id='G-TEST1234')
        self.assertIn(
            '"page_location": "https://testserver/products/lamp/?utm_source=newsletter"', html
        )
        self.assertIn('"page_referrer": "https://www.google.com/"', html)
        self.assertIn(f'{ENTRY_COOKIE}=;Max-Age=0', html)

    def test_a_container_gets_them_in_the_data_layer(self):
        html = self._render(gtm_container_id='GTM-ABC1234')
        self.assertIn('dataLayer.push({"page_location"', html)

    def test_nothing_without_a_carried_entry(self):
        html = self._render(carried=False, measurement_id='G-TEST1234')
        self.assertNotIn('page_referrer', html)
        self.assertNotIn(ENTRY_COOKIE, html)
