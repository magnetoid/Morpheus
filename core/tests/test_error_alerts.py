"""The error log tells a person.

Server errors were captured into ErrorEvent and shown on /dashboard/errors/,
which nobody opened: a product page returned 500 for ten days before anyone
looked. A daily digest now emails the operator the day's server errors, grouped,
and nothing on a clean day.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from core.errors.alerts import alert_recipients, send_digest
from core.errors.models import ErrorEvent


def _error(fingerprint, cls='ValueError', path='/products/orb/'):
    ErrorEvent.objects.create(
        kind=ErrorEvent.KIND_SERVER,
        level=ErrorEvent.LEVEL_ERROR,
        fingerprint=fingerprint,
        exception_class=cls,
        message='boom',
        path=path,
    )


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', ERROR_ALERT_EMAILS=''
)
class ErrorDigestTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(
            username='owner', email='owner@example.com', password='x', is_superuser=True
        )

    def test_the_day_s_errors_are_emailed_grouped(self):
        for _ in range(3):
            _error('aaa')
        _error('bbb', cls='KeyError', path='/cart/')
        self.assertEqual(send_digest(), 4)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['owner@example.com'])
        self.assertIn('4 errors', message.subject)
        self.assertIn('3× ValueError on /products/orb/', message.body)
        self.assertIn('1× KeyError on /cart/', message.body)

    def test_a_clean_day_sends_nothing(self):
        self.assertEqual(send_digest(), 0)
        self.assertEqual(mail.outbox, [])

    def test_recipients_prefer_the_configured_list_then_operators(self):
        with override_settings(ERROR_ALERT_EMAILS='ops@example.com, oncall@example.com'):
            self.assertEqual(alert_recipients(), ['ops@example.com', 'oncall@example.com'])
        self.assertEqual(alert_recipients(), ['owner@example.com'])
