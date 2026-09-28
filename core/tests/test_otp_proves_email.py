"""Signing in with an emailed code announces that the email is proven.

The code reached the inbox, so the person controls the address. Anything that
grants data filed under an email (orders' guest-order linking) waits for this
event rather than for signup, where verification is optional.
"""

from __future__ import annotations

from django.test import TestCase

from core.auth.services import issue_otp
from core.hooks import MorpheusEvents, hook_registry


class OtpSignInProvesEmailTests(TestCase):
    def test_a_code_sign_in_announces_the_verified_email(self):
        code, _ = issue_otp('ana@example.com')
        session = self.client.session
        session['morph_otp_email'] = 'ana@example.com'
        session.save()
        seen = []

        def handler(customer=None, email='', **kwargs):
            seen.append(email)

        hook_registry.register(MorpheusEvents.CUSTOMER_EMAIL_VERIFIED, handler, plugin=None)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.CUSTOMER_EMAIL_VERIFIED, handler)
        self.client.post('/auth/otp/verify/', {'code': code})
        self.assertEqual(seen, ['ana@example.com'])

    def test_a_wrong_code_announces_nothing(self):
        issue_otp('ana@example.com')
        session = self.client.session
        session['morph_otp_email'] = 'ana@example.com'
        session.save()
        seen = []

        def handler(customer=None, email='', **kwargs):
            seen.append(email)

        hook_registry.register(MorpheusEvents.CUSTOMER_EMAIL_VERIFIED, handler, plugin=None)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.CUSTOMER_EMAIL_VERIFIED, handler)
        self.client.post('/auth/otp/verify/', {'code': '000000'})
        self.assertEqual(seen, [])
