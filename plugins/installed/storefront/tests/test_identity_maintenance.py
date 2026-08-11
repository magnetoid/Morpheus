"""Merchant store identity + maintenance mode must reach the storefront.

Settings -> General writes a StoreSettings row, but the storefront read the
store name from an env var and served a hardcoded favicon, so editing either
changed nothing. And `maintenance_mode` had zero consumers: flipping it left
the shop wide open.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import StoreSettings
from plugins.registry import app_registry


class StoreIdentityTests(TestCase):
    def test_store_name_from_the_db_row_reaches_the_page(self):
        StoreSettings.objects.create(store_name='Marko Books')
        body = self.client.get('/').content.decode()
        self.assertIn('Marko Books', body)

    def test_no_row_falls_back_to_the_env_default(self):
        # An unconfigured install must behave exactly as before.
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('dot books', resp.content.decode())

    def test_favicon_falls_back_to_the_builtin_mark(self):
        resp = self.client.get('/favicon.ico')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('svg', resp['Content-Type'])


class MaintenanceModeTests(TestCase):
    def setUp(self):
        self.plugin = app_registry.get('storefront')
        self.addCleanup(self._restore)
        self._orig = self.plugin.get_config_value('maintenance_mode', False)

    def _restore(self):
        self.plugin.set_config('maintenance_mode', self._orig)

    def _close(self, message='Renovating the shelves.'):
        self.plugin.set_config('maintenance_mode', True)
        self.plugin.set_config('maintenance_message', message)

    def test_off_by_default_storefront_is_open(self):
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_on_closes_the_storefront_with_503(self):
        self._close()
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 503)
        self.assertIn('Renovating the shelves.', resp.content.decode())
        self.assertEqual(resp['Retry-After'], '3600')

    def test_staff_can_still_browse_the_closed_shop(self):
        self._close()
        staff = get_user_model().objects.create_user(
            username='mm-staff', email='s@x.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_health_probes_are_never_gated(self):
        # Closing the shop must not make the orchestrator recycle the container.
        self._close()
        self.assertEqual(self.client.get('/readyz').status_code, 200)

    def test_payment_webhooks_are_never_gated(self):
        self._close()
        # Not 503 — an in-flight payment callback must still be accepted.
        self.assertNotEqual(self.client.get('/payments/webhooks/stripe/').status_code, 503)

    def test_dashboard_is_never_gated(self):
        self._close()
        self.assertNotEqual(self.client.get('/dashboard/').status_code, 503)
