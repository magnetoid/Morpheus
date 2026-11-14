"""The Tracking page says what runs, half by half.

The page called tracking "not configured" unless both the GA4 measurement ID
and the API secret were set, while the browser tag runs on the measurement ID
alone (gtag.js) or on a GTM container, since v0.127.0. A store with its tag
live in every visitor's browser was told nothing was set up.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.tracking.models import TrackingSettings

_PAGE = '/dashboard/tracking/'
_NONE = 'Tracking is not configured yet'
_SERVER = 'data-tracking-server-missing'
_BROWSER = 'data-tracking-browser-missing'


class OverviewStatusTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username='track-staff', email='track@example.test', password='x', is_staff=True
        )
        staff.is_superuser = True
        staff.save()
        self.client.force_login(staff)

    def _page(self, **fields) -> str:
        s = TrackingSettings.get_solo()
        for key, value in fields.items():
            setattr(s, key, value)
        s.save()
        response = self.client.get(_PAGE)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_nothing_set_says_not_configured(self):
        html = self._page(measurement_id='', api_secret='', gtm_container_id='')
        self.assertIn(_NONE, html)

    def test_a_measurement_id_alone_runs_the_browser_tag(self):
        html = self._page(measurement_id='G-J08RP43ZK2', api_secret='', gtm_container_id='')
        self.assertNotIn(_NONE, html)
        self.assertIn(_SERVER, html)
        self.assertNotIn(_BROWSER, html)

    def test_a_gtm_container_alone_runs_the_browser_tag(self):
        html = self._page(measurement_id='', api_secret='', gtm_container_id='GTM-ABC123')
        self.assertNotIn(_NONE, html)
        self.assertIn(_SERVER, html)

    def test_both_halves_set_shows_no_note(self):
        html = self._page(measurement_id='G-J08RP43ZK2', api_secret='secret', gtm_container_id='')
        for marker in (_NONE, _SERVER, _BROWSER):
            self.assertNotIn(marker, html)

    def test_server_firing_switched_off_is_not_a_gap(self):
        html = self._page(measurement_id='G-J08RP43ZK2', api_secret='', server_side_enabled=False)
        self.assertNotIn(_NONE, html)
        self.assertNotIn(_SERVER, html)

    def test_client_firing_switched_off_with_the_server_set_says_so(self):
        html = self._page(
            measurement_id='G-J08RP43ZK2', api_secret='secret', client_side_enabled=False
        )
        self.assertNotIn(_NONE, html)
        self.assertIn(_BROWSER, html)

    def test_a_malformed_id_does_not_count(self):
        """The browser tag prints only an id shaped like one (the field is free text)."""
        html = self._page(measurement_id='my analytics', api_secret='', gtm_container_id='')
        self.assertIn(_NONE, html)
