"""C2 — a scheduled campaign goes out at its time; one more than a day late does not."""

from __future__ import annotations

from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from plugins.installed.marketing.models import EmailCampaign
from plugins.installed.newsletter.models import NewsletterSubscriber
from plugins.installed.newsletter.tasks import send_campaign, send_due_campaigns


def _campaign(**kw):
    defaults = {'name': 'Picks', 'subject': 'Five picks', 'html_body': '<p>Hi</p>'}
    defaults.update(kw)
    return EmailCampaign.objects.create(**defaults)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class DueCampaignTests(TestCase):
    def setUp(self):
        NewsletterSubscriber.objects.create(email='r@example.com', status='confirmed')
        self.now = timezone.now()

    def test_due_campaign_starts(self):
        c = _campaign(status='scheduled', scheduled_at=self.now - timedelta(minutes=1))
        send_due_campaigns()
        c.refresh_from_db()
        self.assertEqual(c.status, 'sent')
        self.assertEqual(len(mail.outbox), 1)

    def test_future_campaign_waits(self):
        c = _campaign(status='scheduled', scheduled_at=self.now + timedelta(hours=1))
        send_due_campaigns()
        c.refresh_from_db()
        self.assertEqual(c.status, 'scheduled')
        self.assertEqual(mail.outbox, [])

    def test_more_than_a_day_late_goes_back_to_draft(self):
        from plugins.installed.newsletter.campaigns import is_missed

        when = self.now - timedelta(hours=25)
        c = _campaign(status='scheduled', scheduled_at=when)
        out = send_due_campaigns()
        c.refresh_from_db()
        self.assertEqual(c.status, 'draft')
        self.assertEqual(c.scheduled_at, when)
        self.assertTrue(is_missed(c))
        self.assertEqual(out, {'started': 0, 'missed': 1})
        self.assertEqual(mail.outbox, [])

    def test_running_twice_sends_once(self):
        c = _campaign(status='scheduled', scheduled_at=self.now - timedelta(minutes=1))
        send_due_campaigns()
        send_due_campaigns()
        send_campaign.delay(str(c.id))
        self.assertEqual(len(mail.outbox), 1)

    def test_beat_entry_names_the_registered_task(self):
        from django.conf import settings

        from morph.celery import app

        entry = settings.CELERY_BEAT_SCHEDULE['newsletter:send_due_campaigns']
        self.assertEqual(entry['task'], 'newsletter.send_due_campaigns')
        self.assertEqual(entry['schedule'], 300)
        self.assertIn('newsletter.send_due_campaigns', app.tasks)


class ScheduleRulesTests(TestCase):
    def test_schedule_refuses_the_past(self):
        from plugins.installed.newsletter.campaigns import CampaignError, schedule_campaign

        with self.assertRaisesMessage(CampaignError, 'Pick a time in the future.'):
            schedule_campaign(_campaign(), timezone.now() - timedelta(minutes=1))

    def test_schedule_refuses_a_sent_campaign(self):
        from plugins.installed.newsletter.campaigns import CampaignError, schedule_campaign

        with self.assertRaisesMessage(CampaignError, 'is sent and cannot be scheduled'):
            schedule_campaign(_campaign(status='sent'), timezone.now() + timedelta(hours=1))

    def test_schedule_sets_status_and_time(self):
        from plugins.installed.newsletter.campaigns import schedule_campaign

        c = _campaign()
        when = timezone.now() + timedelta(hours=2)
        schedule_campaign(c, when)
        c.refresh_from_db()
        self.assertEqual((c.status, c.scheduled_at), ('scheduled', when))

    def test_cancel_returns_to_editable_draft(self):
        from plugins.installed.newsletter.campaigns import cancel_campaign

        c = _campaign(status='scheduled', scheduled_at=timezone.now() + timedelta(hours=1))
        cancel_campaign(c)
        c.refresh_from_db()
        self.assertEqual((c.status, c.scheduled_at), ('draft', None))

    def test_cancel_refuses_a_draft(self):
        from plugins.installed.newsletter.campaigns import CampaignError, cancel_campaign

        with self.assertRaises(CampaignError):
            cancel_campaign(_campaign())
