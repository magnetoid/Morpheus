"""Notifications smoke test — notify() creates a row and unread counter
sees it."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase


class NotificationsSmoke(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='staff@example.com', email='staff@example.com',
            password='hunter2', is_staff=True,
        )

    def test_notify_creates_unread_row(self):
        from plugins.installed.notifications_center import services
        services.notify(user=self.user, kind='rma',
                        title='New return request',
                        body='Order #1234 — defective copy',
                        action_url='/dashboard/returns/abc/')
        from plugins.installed.notifications_center.models import Notification
        rows = Notification.objects.filter(user=self.user)
        self.assertEqual(rows.count(), 1)
        self.assertIsNone(rows[0].read_at)
        self.assertEqual(rows[0].kind, 'rma')
