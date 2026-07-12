# plugins/installed/analytics/tests/test_consent_gating.py
"""Non-consented visitors must not mint AnalyticsSession rows (one per
request today — inflates `sessions`) and must not receive the cookie."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.analytics.models import AnalyticsEvent, AnalyticsSession


class ConsentGatingTests(TestCase):
    def test_no_session_without_consent(self):
        self.client.get('/')
        self.client.get('/')
        self.assertEqual(AnalyticsSession.objects.count(), 0)

    def test_pageview_still_recorded_sessionless(self):
        self.client.get('/')
        evt = AnalyticsEvent.objects.filter(kind='pageview').first()
        self.assertIsNotNone(evt)
        self.assertIsNone(evt.session_id)

    def test_consented_visitor_gets_one_session(self):
        self.client.cookies['morpheus_consent'] = '{"analytics": true, "functional": true, "marketing": true}'
        self.client.get('/')
        self.client.get('/')
        self.assertEqual(AnalyticsSession.objects.count(), 1)
