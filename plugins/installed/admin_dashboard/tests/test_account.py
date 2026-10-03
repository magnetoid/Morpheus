"""The staff 'Your account' page (/dashboard/me/): editable profile,
security options, and the user's own recent activity."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

ME_URL = '/dashboard/me/'


def _staff(email='me@x.test'):
    u = get_user_model().objects.create_user(
        username=email, email=email, password='pw', is_staff=True, is_superuser=True
    )
    c = Client()
    c.force_login(u)
    return u, c


class AccountPageTests(TestCase):
    def test_page_renders_profile_and_activity_sections(self):
        _u, c = _staff()
        html = c.get(ME_URL).content.decode()
        self.assertEqual(c.get(ME_URL).status_code, 200)
        # Editable profile fields are present.
        self.assertIn('name="first_name"', html)
        self.assertIn('name="last_name"', html)
        self.assertIn('Account details', html)
        self.assertIn('Your recent activity', html)

    def test_update_profile_persists(self):
        u, c = _staff()
        resp = c.post(
            ME_URL,
            {
                'action': 'update_profile',
                'first_name': 'Ada',
                'last_name': 'Lovelace',
                'phone': '+100',
            },
        )
        self.assertEqual(resp.status_code, 302)
        u.refresh_from_db()
        self.assertEqual(u.first_name, 'Ada')
        self.assertEqual(u.last_name, 'Lovelace')
        self.assertEqual(u.get_full_name(), 'Ada Lovelace')
        # phone is a Customer extra — persisted too when present.
        if hasattr(u, 'phone'):
            self.assertEqual(u.phone, '+100')

    def test_recent_activity_lists_users_own_events(self):
        from core.audit.models import AuditEvent

        u, c = _staff('actor@x.test')
        AuditEvent.objects.create(event_type='catalog.product_updated', actor=u, target='SKU-1')
        AuditEvent.objects.create(event_type='other.thing', actor=None, target='system')

        from plugins.installed.admin_dashboard.views_split.account import (
            _account_recent_activity,
        )

        rows = _account_recent_activity(u)
        # Only the user's own action: not the system event, and not the
        # sign-in that _staff() just recorded.
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['event_type'], 'catalog.product_updated')
        self.assertIn('catalog', rows[0]['label'])

    def test_requires_staff(self):
        resp = Client().get(ME_URL)  # anonymous
        self.assertIn(resp.status_code, (302, 403))
