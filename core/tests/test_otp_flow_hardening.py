"""The email sign-in code: where it sends you, what it stores, and when it refuses.

- `?next=` must stay on this site. Browsers read `\\` as `/`, so `/\\evil.example`
  and `/\\t/evil.example` used to pass a `startswith('/')` check and leave it.
- The address stored with a code (an inet column on Postgres) and used in the
  limiter key is a validated IP or nothing: X-Forwarded-For is whatever the
  visitor sent, and `unknown` there was a DataError (500) on Postgres.
- A failed send is logged; the visitor sees the same next step either way.
- While the cache is down nothing counts wrong codes, so no code is tried.
"""

from __future__ import annotations

import smtplib
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.auth.models import EmailOTP
from core.auth.services import issue_otp, send_otp_email
from core.auth.views import _safe_next
from core.ratelimit import client_ip_address


class SafeNextTests(SimpleTestCase):
    def _next(self, value, **extra):
        return _safe_next(RequestFactory().get('/auth/otp/', {'next': value}, **extra))

    def test_a_path_on_this_site_is_kept(self):
        self.assertEqual(self._next('/account/orders/'), '/account/orders/')

    def test_anything_that_leaves_the_site_falls_back(self):
        for value in (
            '/\\evil.example',
            '/\\t/evil.example',
            '/\t/evil.example',
            '//evil.example',
            'https://evil.example/',
            'javascript:alert(1)',
        ):
            self.assertEqual(self._next(value), '/account/', repr(value))


class ClientIpAddressTests(SimpleTestCase):
    def _ip(self, **meta):
        return client_ip_address(RequestFactory().get('/', **meta))

    def test_a_header_that_is_no_address_gives_none(self):
        self.assertIsNone(self._ip(HTTP_X_FORWARDED_FOR='unknown', REMOTE_ADDR='not-an-ip'))

    def test_the_first_forwarded_address(self):
        self.assertEqual(self._ip(HTTP_X_FORWARDED_FOR='203.0.113.9, 10.0.0.1'), '203.0.113.9')

    def test_cloudflare_comes_first(self):
        self.assertEqual(
            self._ip(HTTP_CF_CONNECTING_IP='198.51.100.4', HTTP_X_FORWARDED_FOR='203.0.113.9'),
            '198.51.100.4',
        )


class OtpRequestTests(TestCase):
    def test_a_forged_forwarded_header_stores_no_address(self):
        self.client.post(
            reverse('core_auth:otp_request'),
            {'email': 'shopper@example.com'},
            HTTP_X_FORWARDED_FOR='unknown',
        )
        self.assertIsNone(EmailOTP.objects.get(email='shopper@example.com').request_ip)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST='smtp.invalid'
    )
    def test_a_failed_send_is_logged_and_the_visitor_goes_on(self):
        with patch('smtplib.SMTP', side_effect=smtplib.SMTPConnectError(421, 'down')):
            with self.assertLogs('morpheus.core.auth', 'WARNING'):
                send_otp_email(to='shopper@example.com', code='123456')
            with self.assertLogs('morpheus.core.auth', 'WARNING'):
                response = self.client.post(
                    reverse('core_auth:otp_request'), {'email': 'shopper@example.com'}
                )
        self.assertRedirects(
            response, reverse('core_auth:otp_verify'), fetch_redirect_response=False
        )


class OtpVerifyCacheDownTests(TestCase):
    def setUp(self):
        self.email = 'shopper@example.com'
        self.code, _ = issue_otp(self.email)
        session = self.client.session
        session['morph_otp_email'] = self.email
        session.save()

    def test_no_code_is_tried_while_nothing_can_count(self):
        # django-redis with IGNORE_EXCEPTIONS answers None when Redis is down.
        with patch('core.auth.views.cache.add', return_value=None):
            response = self.client.post(reverse('core_auth:otp_verify'), {'code': self.code})
        self.assertEqual(response.status_code, 429)
        self.assertIsNone(self.client.session.get('_auth_user_id'))
        self.assertTrue(EmailOTP.objects.filter(consumed_at__isnull=True).exists())

    def test_a_wrong_code_when_the_count_is_lost_is_no_500(self):
        with patch('core.auth.views.cache.incr', return_value=None):
            response = self.client.post(reverse('core_auth:otp_verify'), {'code': '000000'})
        self.assertEqual(response.status_code, 200)
