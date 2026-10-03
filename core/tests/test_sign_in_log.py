"""Every sign-in lands in the audit log, so the dashboard can show when each
customer or admin signed in, from which address and on what device.

It is recorded from Django's ``user_logged_in`` signal, which every sign-in
route sends: emailed code, password (allauth), two-factor and SSO.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.audit.models import AuditEvent
from core.audit.services import record
from core.auth.services import issue_otp
from core.auth.sign_ins import describe_device, prune_sign_ins, recent_sign_ins

CHROME_MAC = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
)


def sign_in_with_code(client, email, **headers):
    code, _ = issue_otp(email)
    session = client.session
    session['morph_otp_email'] = email
    session.save()
    return client.post('/auth/otp/verify/', {'code': code}, **headers)


class SignInLogTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='ana', email='ana@example.com', password='correct-horse-battery'
        )

    def test_a_code_sign_in_records_time_address_and_device(self):
        before = timezone.now()
        sign_in_with_code(
            self.client,
            'ana@example.com',
            HTTP_CF_CONNECTING_IP='203.0.113.7',
            HTTP_USER_AGENT=CHROME_MAC,
        )
        [row] = recent_sign_ins(self.user)
        self.assertEqual(row['ip'], '203.0.113.7')
        self.assertEqual(row['device'], 'Chrome on Mac')
        self.assertGreaterEqual(row['at'], before)

    def test_a_password_sign_in_is_recorded(self):
        self.client.post(
            '/auth/login/', {'login': 'ana@example.com', 'password': 'correct-horse-battery'}
        )
        self.assertEqual(len(recent_sign_ins(self.user)), 1)

    def test_a_wrong_password_records_nothing(self):
        self.client.post('/auth/login/', {'login': 'ana@example.com', 'password': 'wrong-guess'})
        self.assertEqual(recent_sign_ins(self.user), [])

    def test_the_cloudflare_address_beats_a_forged_forwarded_for(self):
        # X-Forwarded-For's first entry is whatever the visitor sent.
        sign_in_with_code(
            self.client,
            'ana@example.com',
            HTTP_CF_CONNECTING_IP='203.0.113.7',
            HTTP_X_FORWARDED_FOR='198.51.100.66',
        )
        self.assertEqual(recent_sign_ins(self.user)[0]['ip'], '203.0.113.7')

    def test_only_this_persons_sign_ins_are_listed(self):
        other = get_user_model().objects.create_user(
            username='bo', email='bo@example.com', password='x'
        )
        self.client.force_login(other)
        self.assertEqual(recent_sign_ins(self.user), [])

    def test_the_ten_newest_are_listed_newest_first(self):
        for _ in range(12):
            self.client.force_login(self.user)
        base = timezone.now() - timedelta(days=1)
        for i, pk in enumerate(
            AuditEvent.objects.filter(actor=self.user)
            .order_by('created_at')
            .values_list('pk', flat=True)
        ):
            AuditEvent.objects.filter(pk=pk).update(created_at=base + timedelta(minutes=i))
        rows = recent_sign_ins(self.user)
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]['at'], base + timedelta(minutes=11))
        self.assertEqual(rows[-1]['at'], base + timedelta(minutes=2))

    def test_prune_drops_sign_ins_older_than_90_days_and_nothing_else(self):
        self.client.force_login(self.user)
        self.client.force_login(self.user)
        old_pk, recent_pk = AuditEvent.objects.filter(actor=self.user).values_list('pk', flat=True)
        now = timezone.now()
        AuditEvent.objects.filter(pk=old_pk).update(created_at=now - timedelta(days=91))
        AuditEvent.objects.filter(pk=recent_pk).update(created_at=now - timedelta(days=89))
        other = record(event_type='rbac.role_granted', actor=self.user, target='user/x')
        AuditEvent.objects.filter(pk=other.pk).update(created_at=now - timedelta(days=400))

        self.assertEqual(prune_sign_ins(), 1)
        self.assertFalse(AuditEvent.objects.filter(pk=old_pk).exists())
        self.assertTrue(AuditEvent.objects.filter(pk=recent_pk).exists())
        self.assertTrue(AuditEvent.objects.filter(pk=other.pk).exists())


class DescribeDeviceTests(SimpleTestCase):
    def test_common_browsers_and_devices(self):
        cases = {
            CHROME_MAC: 'Chrome on Mac',
            (
                'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 '
                '(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'
            ): 'Safari on iPhone',
            (
                'Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 '
                '(KHTML, like Gecko) CriOS/128.0 Mobile/15E148 Safari/604.1'
            ): 'Chrome on iPad',
            (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0'
            ): 'Firefox on Windows',
            (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0'
            ): 'Edge on Windows',
            (
                'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/128.0.0.0 Mobile Safari/537.36'
            ): 'Chrome on Android',
            '': 'Unknown device',
            'curl/8.4.0': 'Unknown device',
        }
        for user_agent, want in cases.items():
            with self.subTest(user_agent=user_agent[:50]):
                self.assertEqual(describe_device(user_agent), want)
