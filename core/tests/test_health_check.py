"""The nightly health check records and emails what would stop the store selling.

Each app contributes the checks only it can make (HEALTH_CHECKS); a failure is
written to the error log and emailed the same night. Page fetches are faked —
tests never touch the network.
"""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from core.errors.health import run_and_report, run_checks
from core.errors.models import ErrorEvent
from core.hooks import MorpheusEvents, hook_registry

PAGES_OK = mock.patch('requests.get', return_value=mock.Mock(status_code=200))


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_HOST='smtp.example.com',
    ERROR_ALERT_EMAILS='ops@example.com',
)
class HealthCheckTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(username='hc', email='hc@example.com', password='x')

    def test_every_app_contributes_its_check(self):
        with PAGES_OK:
            names = {r['name'] for r in run_checks()}
        for name in ('Outgoing email is set up', 'Order email templates load',
                     'Checkout can take payment', 'A cart can be priced', 'Shop pages load'):  # fmt: skip
            with self.subTest(check=name):
                self.assertIn(name, names)

    def test_a_failing_check_is_recorded_and_emailed(self):
        def broken(value, **kwargs):
            value.append({'name': 'Probe', 'ok': False, 'detail': 'probe says no'})
            return value

        hook_registry.register(MorpheusEvents.HEALTH_CHECKS, broken, plugin=None)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.HEALTH_CHECKS, broken)
        with PAGES_OK:
            failed = [r['name'] for r in run_and_report()]
        self.assertIn('Probe', failed)
        self.assertTrue(ErrorEvent.objects.filter(message__icontains='probe says no').exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Probe: probe says no', mail.outbox[0].body)

    def test_a_page_that_errors_fails_the_check(self):
        def fake_get(url, **kwargs):
            return mock.Mock(status_code=500 if url.endswith('/cart/') else 200)

        with mock.patch('requests.get', side_effect=fake_get):
            pages = next(r for r in run_checks() if r['name'] == 'Shop pages load')
        self.assertFalse(pages['ok'])
        self.assertIn('/cart/ → 500', pages['detail'])

    @override_settings(EMAIL_HOST='')
    def test_a_store_that_cannot_send_email_fails(self):
        with PAGES_OK:
            email = next(r for r in run_checks() if r['name'] == 'Outgoing email is set up')
        self.assertFalse(email['ok'])
