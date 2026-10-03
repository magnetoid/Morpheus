"""The Contacts list (customers and its Admins tab) shows when each person last
signed in, and each person's page lists their recent sign-ins."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.auth.services import issue_otp

CHROME_MAC = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
)


def _row(body: str, email: str) -> str:
    """The table row that carries this email ('' when there is none)."""
    m = re.search(r'<tr\b(?:(?!</tr>).)*' + re.escape(email) + r'(?:(?!</tr>).)*</tr>', body, re.S)
    return m.group(0) if m else ''


class ContactsSignInTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(
            username='ops', email='ops@example.com', password='x', is_staff=True
        )
        self.client.force_login(self.staff)
        self.seen = User.objects.create_user(
            username='seen', email='seen@example.com', password='x'
        )
        User.objects.filter(pk=self.seen.pk).update(
            last_login=datetime(2026, 9, 30, 17, 12, tzinfo=UTC)
        )
        self.never = User.objects.create_user(
            username='never', email='never@example.com', password='x'
        )

    def test_the_list_shows_when_each_person_last_signed_in(self):
        body = self.client.get(reverse('admin_dashboard:customers')).content.decode()
        self.assertIn('Sep 30, 2026 17:12', _row(body, 'seen@example.com'))
        self.assertIn('Never', _row(body, 'never@example.com'))

    def test_the_admins_tab_shows_it_too(self):
        # A fixed time that can't be confused with today's "Joined" date.
        get_user_model().objects.filter(pk=self.staff.pk).update(
            last_login=datetime(2026, 9, 29, 11, 3, tzinfo=UTC)
        )
        body = self.client.get(reverse('admin_dashboard:customers') + '?admin=1').content.decode()
        self.assertIn('Sep 29, 2026 11:03', _row(body, 'ops@example.com'))

    def test_newest_sign_in_first_and_never_signed_in_last(self):
        User = get_user_model()
        older = User.objects.create_user(username='older', email='older@example.com', password='x')
        User.objects.filter(pk=older.pk).update(last_login=datetime(2026, 9, 1, 8, 0, tzinfo=UTC))
        body = self.client.get(
            reverse('admin_dashboard:customers') + '?sort=last_sign_in&dir=desc'
        ).content.decode()
        self.assertLess(body.index('seen@example.com'), body.index('older@example.com'))
        self.assertLess(body.index('older@example.com'), body.index('never@example.com'))

    def test_a_persons_page_lists_their_recent_sign_ins(self):
        shopper = Client()
        code, _ = issue_otp('seen@example.com')
        session = shopper.session
        session['morph_otp_email'] = 'seen@example.com'
        session.save()
        shopper.post(
            '/auth/otp/verify/',
            {'code': code},
            HTTP_CF_CONNECTING_IP='203.0.113.7',
            HTTP_USER_AGENT=CHROME_MAC,
        )
        body = self.client.get(
            reverse('admin_dashboard:customer_edit', args=[self.seen.pk])
        ).content.decode()
        self.assertIn('203.0.113.7', body)
        self.assertIn('Chrome on Mac', body)

    def test_a_sign_in_from_before_the_log_still_shows_its_time(self):
        # seen's last_login predates the log, so there are no details on record.
        body = self.client.get(
            reverse('admin_dashboard:customer_edit', args=[self.seen.pk])
        ).content.decode()
        self.assertIn('Last signed in Sep 30, 2026 17:12', body)
        self.assertNotIn('No sign-ins yet', body)

    def test_a_person_who_never_signed_in_says_so(self):
        body = self.client.get(
            reverse('admin_dashboard:customer_edit', args=[self.never.pk])
        ).content.decode()
        self.assertIn('No sign-ins yet', body)
