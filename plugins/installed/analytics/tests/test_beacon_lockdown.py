# plugins/installed/analytics/tests/test_beacon_lockdown.py
"""The beacon must not accept client-forgeable money/auth kinds, and must
rate-limit per IP (an open unauthenticated POST endpoint)."""

from __future__ import annotations

import json

from django.core.cache import cache
from django.test import TestCase

from plugins.installed.analytics.models import AnalyticsEvent

_URL = '/api/analytics/track/'


class BeaconKindTests(TestCase):
    def _post(self, kind):
        return self.client.post(
            _URL,
            data=json.dumps({'name': f'evt-{kind}', 'kind': kind}),
            content_type='application/json',
        )

    def test_money_and_auth_kinds_downgrade_to_custom(self):
        for kind in ('purchase', 'checkout', 'signup', 'login'):
            self._post(kind)
            evt = AnalyticsEvent.objects.get(name=f'evt-{kind}')
            self.assertEqual(evt.kind, 'custom', f'{kind} must not be client-settable')


class BeaconRateLimitTests(TestCase):
    # api.rate_limit.RateLimitMiddleware already 429s anonymous /api traffic
    # at 100/min — but hands 600/min to ANY unvalidated `Bearer` header. The
    # beacon's own 120/min limit is the defence for exactly that bypass, so
    # the test sends a junk Bearer to sail past the middleware and prove the
    # view-level limiter fires on its own.
    def setUp(self):
        cache.clear()

    def _post(self, name):
        return self.client.post(
            _URL,
            data=json.dumps({'name': name, 'kind': 'click'}),
            content_type='application/json',
            HTTP_AUTHORIZATION='Bearer junk-forged-token',
        )

    def test_121st_event_in_a_minute_is_429(self):
        for i in range(120):
            resp = self._post(f'e{i}')
            self.assertNotEqual(resp.status_code, 429)
        resp = self._post('e-last')
        self.assertEqual(resp.status_code, 429)
