"""Settings saves must be in-place AJAX (no redirect to a single-panel page).

The settings-category page hosts the core StoreSettings form AND each plugin
SettingsPanel form; both are `data-ajax`, so a save shows a spinner in place and
never navigates. That only works if the server answers the AJAX POST with JSON
(200 {ok:true} on success, 400 {ok:false, errors} on failure) instead of a 302
redirect — otherwise dashboard.js reads the non-JSON 200 as a false "Saved"
(the dashboard AJAX JSON-contract landmine).
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

_AJAX = {'X-Requested-With': 'XMLHttpRequest'}


class _StaffClientMixin(TestCase):
    def setUp(self):
        self.client = Client()
        staff = get_user_model().objects.create_user(
            username='setstaff', email='setstaff@x.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)


class CoreFormAjaxSaveTests(_StaffClientMixin):
    def _url(self):
        return reverse('admin_dashboard:settings_category', kwargs={'category': 'general'})

    def test_valid_ajax_post_returns_json_ok_not_redirect(self):
        resp = self.client.post(
            self._url(),
            {
                '_form': 'core',
                'store_name': 'Ajax Store',
                'primary_currency': 'USD',
                'country': 'US',
            },
            headers=_AJAX,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'].split(';')[0], 'application/json')
        self.assertTrue(resp.json()['ok'])

    def test_invalid_ajax_post_returns_json_errors(self):
        # Blank required store_name → validation failure must be JSON, not a
        # silently-successful HTML re-render.
        resp = self.client.post(
            self._url(),
            {'_form': 'core', 'store_name': ''},
            headers=_AJAX,
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['ok'])
        self.assertIn('store_name', data['errors'])

    def test_non_ajax_post_still_redirects(self):
        resp = self.client.post(
            self._url(),
            {
                '_form': 'core',
                'store_name': 'Classic Store',
                'primary_currency': 'USD',
                'country': 'US',
            },
        )
        self.assertIn(resp.status_code, (302, 303))
