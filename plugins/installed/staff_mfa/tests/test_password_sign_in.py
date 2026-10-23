"""Every allauth sign-in runs the second factor (v0.123.2).

allauth's own sign-ins (email and password at /auth/login/, a code, a sign-up, a password
reset, a social login) never fired AUTH_SECOND_FACTOR, so a staff member with an
authenticator who signed in with a password reached the dashboard on the password alone.
core.auth.adapters.AccountAdapter.pre_login now fires it before allauth logs anyone in, and
fails closed the way otp_verify does.
"""

from __future__ import annotations

import pyotp
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from morpheus.core import hook_registry
from plugins.installed.staff_mfa import services
from plugins.installed.staff_mfa.models import StaffMfaDevice

PASSWORD = 'S3cure-pass-7f3a!'


def _user(email, *, staff):
    return get_user_model().objects.create_user(
        username=email, email=email, password=PASSWORD, is_staff=staff
    )


def _confirmed_device(user):
    from django.utils import timezone

    return StaffMfaDevice.objects.create(
        user=user, secret=services.new_secret(), confirmed_at=timezone.now()
    )


class PasswordSignInSecondFactorTests(TestCase):
    def _sign_in(self, email):
        return self.client.post(reverse('account_login'), {'login': email, 'password': PASSWORD})

    def test_an_enrolled_staff_member_is_asked_for_the_code(self):
        user = _user('boss@example.com', staff=True)
        _confirmed_device(user)
        resp = self._sign_in('boss@example.com')
        self.assertRedirects(resp, reverse('staff_mfa:challenge'), fetch_redirect_response=False)
        self.assertIsNone(self.client.session.get('_auth_user_id'))
        self.assertEqual(self.client.session.get('mfa_pending_user_id'), str(user.pk))

    def test_the_code_then_completes_the_sign_in(self):
        user = _user('boss@example.com', staff=True)
        device = _confirmed_device(user)
        self._sign_in('boss@example.com')
        code = pyotp.TOTP(device.secret).now()
        resp = self.client.post(reverse('staff_mfa:challenge'), {'code': code})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.session.get('_auth_user_id'), str(user.pk))

    def test_a_customer_signs_in_with_a_password_as_before(self):
        user = _user('shopper@example.com', staff=False)
        self._sign_in('shopper@example.com')
        self.assertEqual(self.client.session.get('_auth_user_id'), str(user.pk))

    def test_a_failing_second_factor_refuses_the_sign_in(self):
        def boom(value, **kwargs):
            raise RuntimeError('second-factor backend down')

        # Earlier than the real subscriber: an unenrolled staffer would otherwise sail through.
        hook_registry.register('auth.second_factor', boom, priority=1)
        self.addCleanup(hook_registry.unregister, 'auth.second_factor', boom)
        _user('boss@example.com', staff=True)
        self._sign_in('boss@example.com')
        self.assertIsNone(self.client.session.get('_auth_user_id'))
