"""The second-factor challenge stays on this site and stores a real address.

`mfa_next` came from a `startswith('/')` check, and browsers read `\\` as `/`, so
`/\\evil.example` sent a staff member off the site right after they signed in.
The audit row's address was the raw first X-Forwarded-For entry, which the
visitor writes.
"""

from __future__ import annotations

import pyotp
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from core.audit.models import AuditEvent
from plugins.installed.staff_mfa import services
from plugins.installed.staff_mfa.models import StaffMfaDevice


class ChallengeNextTests(TestCase):
    def _sign_in(self, nxt):
        user = get_user_model().objects.create_user(
            username='boss@example.com', email='boss@example.com', password='pw', is_staff=True
        )
        device = StaffMfaDevice.objects.create(
            user=user, secret=services.new_secret(), confirmed_at=timezone.now()
        )
        session = self.client.session
        session['mfa_pending_user_id'] = str(user.pk)
        session['mfa_next'] = nxt
        session.save()
        code = pyotp.TOTP(device.secret).now()
        return self.client.post(reverse('staff_mfa:challenge'), {'code': code})

    def test_a_backslash_next_stays_on_the_site(self):
        self.assertEqual(self._sign_in('/\\evil.example').headers['Location'], '/dashboard/')

    def test_a_path_on_the_site_is_kept(self):
        self.assertEqual(
            self._sign_in('/dashboard/orders/').headers['Location'], '/dashboard/orders/'
        )


class AuditAddressTests(TestCase):
    def test_a_forged_forwarded_header_is_not_stored(self):
        request = RequestFactory().get('/', HTTP_X_FORWARDED_FOR='unknown')
        services.audit('mfa.challenge_failed', request=request)
        self.assertIsNone(AuditEvent.objects.get(event_type='mfa.challenge_failed').ip_address)

    def test_the_visitors_address_is_stored(self):
        request = RequestFactory().get('/', HTTP_X_FORWARDED_FOR='203.0.113.9, 10.0.0.1')
        services.audit('mfa.challenge_failed', request=request)
        self.assertEqual(
            AuditEvent.objects.get(event_type='mfa.challenge_failed').ip_address, '203.0.113.9'
        )
