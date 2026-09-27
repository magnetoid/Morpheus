"""Re-sending the double opt-in email to subscribers stuck at `pending`.

Until v0.75.17 the Celery worker never registered the email task, so every
confirmation email queued since 2026-07-12 was discarded: 29 people who asked
to subscribe never received the link and could never confirm.
"""

from __future__ import annotations

from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from plugins.installed.newsletter.models import NewsletterSubscriber


class ResendConfirmationsTests(TestCase):
    def setUp(self):
        NewsletterSubscriber.objects.create(email='reader@example.com', status='pending')
        NewsletterSubscriber.objects.create(email='typo@gmail_com', status='pending')
        NewsletterSubscriber.objects.create(email='done@example.com', status='confirmed')
        mail.outbox = []

    def test_pending_deliverable_subscribers_get_one_confirmation(self):
        out = StringIO()
        call_command('newsletter_resend_confirmations', stdout=out)
        self.assertEqual([m.to for m in mail.outbox], [['reader@example.com']])
        self.assertIn('Re-sent 1', out.getvalue())
        self.assertIn('skipped 1', out.getvalue())

    def test_dry_run_sends_nothing(self):
        out = StringIO()
        call_command('newsletter_resend_confirmations', '--dry-run', stdout=out)
        self.assertEqual(mail.outbox, [])
        self.assertIn('Would re-send 1', out.getvalue())

    def test_since_limits_the_window(self):
        call_command('newsletter_resend_confirmations', '--since', '2999-01-01', stdout=StringIO())
        self.assertEqual(mail.outbox, [])
