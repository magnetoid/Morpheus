"""staff_mfa tests — TOTP contract (real pyotp), recovery codes, the
AUTH_SECOND_FACTOR subscriber, and permission boundaries on the surfaces.

Run:
    DATABASE_URL='sqlite:///:memory:' ... manage.py test plugins.installed.staff_mfa
"""

from __future__ import annotations

import pyotp
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from morpheus.core import hook_registry
from plugins.installed.staff_mfa import services
from plugins.installed.staff_mfa.models import MfaRecoveryCode, StaffMfaDevice


def _staff(email='boss@example.com'):
    return get_user_model().objects.create_user(
        username=email, email=email, password='pw', is_staff=True
    )


def _customer(email='shopper@example.com'):
    return get_user_model().objects.create_user(
        username=email, email=email, password='pw', is_staff=False
    )


def _confirmed_device(user):
    from django.utils import timezone

    return StaffMfaDevice.objects.create(
        user=user, secret=services.new_secret(), confirmed_at=timezone.now()
    )


class TotpContract(TestCase):
    """Hit pyotp's real interface, not a mock."""

    def test_correct_code_passes_wrong_fails(self):
        secret = services.new_secret()
        good = pyotp.TOTP(secret).now()
        self.assertTrue(services.verify_totp(secret, good))
        self.assertFalse(services.verify_totp(secret, '000000'))
        self.assertFalse(services.verify_totp(secret, ''))
        self.assertFalse(services.verify_totp(secret, 'abcdef'))

    def test_provisioning_uri_is_otpauth(self):
        uri = services.provisioning_uri(services.new_secret(), account='a@b.com', issuer='Morpheus')
        self.assertTrue(uri.startswith('otpauth://totp/'))
        self.assertIn('issuer=Morpheus', uri)


class RecoveryCodes(TestCase):
    def setUp(self):
        self.device = _confirmed_device(_staff())

    def test_codes_are_hashed_single_use(self):
        codes = services.generate_recovery_codes(self.device, count=10)
        self.assertEqual(len(codes), 10)
        # Stored as hashes, never plaintext.
        stored = list(
            MfaRecoveryCode.objects.filter(device=self.device).values_list('code_hash', flat=True)
        )
        self.assertEqual(len(stored), 10)
        self.assertNotIn(codes[0], stored)
        # Works once, then is dead.
        self.assertTrue(services.consume_recovery_code(self.device, codes[0]))
        self.assertFalse(services.consume_recovery_code(self.device, codes[0]))
        # A never-issued code never works.
        self.assertFalse(services.consume_recovery_code(self.device, 'deadbeef00'))

    def test_regenerate_replaces_old_codes(self):
        first = services.generate_recovery_codes(self.device, count=5)
        services.generate_recovery_codes(self.device, count=5)
        # Old codes no longer valid after regeneration.
        self.assertFalse(services.consume_recovery_code(self.device, first[0]))


class SecondFactorSubscriber(TestCase):
    """The AUTH_SECOND_FACTOR decision — the heart of the disable/enforce logic."""

    def setUp(self):
        from plugins.registry import app_registry

        self.plugin = app_registry.get('staff_mfa')
        self.rf = RequestFactory()

    def _req(self):
        req = self.rf.get('/auth/otp/verify/')
        req.session = self.client.session
        return req

    def test_subscriber_is_registered_on_core_hook(self):
        # Core fires AUTH_SECOND_FACTOR; the plugin must be subscribed when active.
        self.assertTrue(hook_registry.has_handlers('auth.second_factor'))

    def test_non_staff_never_gated(self):
        resp = services.second_factor_response(self.plugin, self._req(), _customer(), '/account/')
        self.assertIsNone(resp)  # login proceeds unchanged

    def test_staff_without_device_optin_not_gated(self):
        # require_for_staff defaults False → opt-in → unenrolled staff log in normally.
        resp = services.second_factor_response(self.plugin, self._req(), _staff(), '/dashboard/')
        self.assertIsNone(resp)

    def test_enrolled_staff_is_challenged(self):
        user = _staff()
        _confirmed_device(user)
        req = self._req()
        resp = services.second_factor_response(self.plugin, req, user, '/dashboard/orders/')
        self.assertIsNotNone(resp)  # a redirect to the challenge
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(req.session['mfa_pending_user_id'], str(user.pk))
        self.assertEqual(req.session['mfa_next'], '/dashboard/orders/')


class EnrollPermissionBoundary(TestCase):
    """Three-way boundary on the enrollment dashboard page."""

    def setUp(self):
        self.url = '/dashboard/apps/staff_mfa/enroll/'

    def test_anonymous_blocked(self):
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (301, 302, 403))  # redirected to login / denied

    def test_non_staff_blocked(self):
        self.client.force_login(_customer())
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (301, 302, 403))

    def test_staff_allowed(self):
        self.client.force_login(_staff())
        resp = self.client.get(self.url, follow=True)
        self.assertEqual(resp.status_code, 200)


class ChallengeFlow(TestCase):
    """Session-gated challenge view completes login on a valid code."""

    def test_no_pending_redirects_out(self):
        resp = self.client.get(reverse('staff_mfa:challenge'))
        self.assertEqual(resp.status_code, 302)

    def test_valid_totp_logs_in(self):
        user = _staff()
        device = _confirmed_device(user)
        session = self.client.session
        session['mfa_pending_user_id'] = str(user.pk)
        session['mfa_next'] = '/dashboard/'
        session.save()

        code = pyotp.TOTP(device.secret).now()
        resp = self.client.post(reverse('staff_mfa:challenge'), {'code': code})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers['Location'], '/dashboard/')
        # Session is now an authenticated session; pending key cleared.
        self.assertNotIn('mfa_pending_user_id', self.client.session)
        self.assertEqual(self.client.session.get('_auth_user_id'), str(user.pk))

    def test_wrong_code_does_not_log_in(self):
        user = _staff()
        _confirmed_device(user)
        session = self.client.session
        session['mfa_pending_user_id'] = str(user.pk)
        session.save()

        resp = self.client.post(reverse('staff_mfa:challenge'), {'code': '000000'})
        self.assertEqual(resp.status_code, 200)  # re-render with error
        self.assertIsNone(self.client.session.get('_auth_user_id'))


class SecondFactorFailClosed(TestCase):
    """otp_verify must fail CLOSED when a second-factor subscriber raises.

    Regression: the gate rode the fail-soft hook bus, so a raising handler was
    swallowed, `filter` returned None (= "no second factor"), and the staffer
    was logged in single-factor. otp_verify now passes raise_errors=True and
    refuses login on any handler exception.
    """

    def test_raising_second_factor_handler_blocks_login(self):
        from core.auth.services import issue_otp

        def boom(value, **kwargs):
            raise RuntimeError('second-factor backend down')

        # Runs before the real subscriber (lower priority = earlier) so it is
        # the first to raise; an unenrolled staffer would otherwise sail through.
        hook_registry.register('auth.second_factor', boom, priority=1)
        try:
            email = 'boss@example.com'
            _staff(email)
            code, _ = issue_otp(email)
            self.assertIsNotNone(code)

            session = self.client.session
            session['morph_otp_email'] = email
            session['morph_otp_next'] = '/dashboard/'
            session.save()

            resp = self.client.post(reverse('core_auth:otp_verify'), {'code': code})
            # Re-renders the verify page with an error; login refused.
            self.assertEqual(resp.status_code, 200)
            self.assertIsNone(self.client.session.get('_auth_user_id'))
        finally:
            hook_registry.unregister('auth.second_factor', boom)


class AdminResetCommand(TestCase):
    def test_reset_clears_device(self):
        from io import StringIO

        from django.core.management import call_command

        user = _staff('lost@example.com')
        _confirmed_device(user)
        self.assertTrue(StaffMfaDevice.objects.filter(user=user).exists())

        call_command('reset_mfa', 'lost@example.com', stdout=StringIO())
        self.assertFalse(StaffMfaDevice.objects.filter(user=user).exists())


class EnrollConfirmRateLimit(TestCase):
    """The confirm endpoint is throttled so it can't be a TOTP oracle."""

    def test_confirm_is_throttled(self):
        user = _staff()
        StaffMfaDevice.objects.create(user=user, secret=services.new_secret())  # pending
        self.client.force_login(user)
        url = '/dashboard/apps/staff_mfa/enroll/'
        last = None
        for _ in range(6):
            last = self.client.post(url, {'action': 'confirm', 'code': '000000'}, follow=True)
        self.assertContains(last, 'Too many attempts')
