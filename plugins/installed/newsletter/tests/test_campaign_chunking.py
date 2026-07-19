"""Campaign sending is chunked + resumable (deep-debug #20).

``send_campaign`` used to enqueue the ENTIRE confirmed list in one task run, so
a large audience could blow the Celery hard limit and strand the campaign at
'sending' with no way to resume. It now claims, sends one ``CAMPAIGN_BATCH_SIZE``
batch, and re-enqueues a continuation until the audience is exhausted — each run
stays far under the limit, and a wedged 'sending' campaign resumes from the
ledger without double-sending.

Under tests CELERY_TASK_ALWAYS_EAGER is on, so ``.delay`` (including the
self-re-enqueued continuation) runs inline — the whole chain completes within
the first call.
"""

from __future__ import annotations

from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings

from plugins.installed.marketing.models import EmailCampaign
from plugins.installed.newsletter.models import CampaignSend, NewsletterSubscriber
from plugins.installed.newsletter.tasks import send_campaign, send_campaign_continue


def _campaign(**kw):
    defaults = {
        'name': 'July picks',
        'subject': 'Five books for July',
        'html_body': '<p>Our five picks.</p>',
        'text_body': 'Our five picks.',
        'status': 'draft',
    }
    defaults.update(kw)
    return EmailCampaign.objects.create(**defaults)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class CampaignChunkingTests(TestCase):
    def test_list_larger_than_a_batch_is_fully_sent_in_chunks(self):
        for i in range(5):
            NewsletterSubscriber.objects.create(email=f'r{i}@example.com', status='confirmed')
        campaign = _campaign()

        with patch('plugins.installed.newsletter.tasks.CAMPAIGN_BATCH_SIZE', 2):
            out = send_campaign.delay(str(campaign.id)).get()

        # First batch reported partial; the eager continuation chain finished it.
        self.assertTrue(out['ok'])
        self.assertTrue(out.get('partial'))
        self.assertEqual(out['sent'], 2)  # this batch only
        self.assertEqual(len(mail.outbox), 5)  # all five delivered across batches
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'sent')
        self.assertEqual(campaign.recipient_count, 5)
        # Exactly one campaign row per recipient — no batch double-sent.
        self.assertEqual(
            CampaignSend.objects.filter(campaign=campaign, kind='campaign', ok=True).count(), 5
        )

    def test_small_list_finishes_in_one_batch(self):
        NewsletterSubscriber.objects.create(email='solo@example.com', status='confirmed')
        campaign = _campaign()
        out = send_campaign.delay(str(campaign.id)).get()
        self.assertTrue(out['ok'])
        self.assertIsNone(out.get('partial'))  # one batch, no continuation
        self.assertEqual(out['sent'], 1)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'sent')

    def test_continue_resumes_a_wedged_sending_campaign_without_resend(self):
        for i in range(4):
            NewsletterSubscriber.objects.create(email=f's{i}@example.com', status='confirmed')
        # A campaign a crashed prior run left mid-send: 'sending', 2 already logged.
        campaign = _campaign(status='sending')
        CampaignSend.objects.create(campaign=campaign, email='s0@example.com')
        CampaignSend.objects.create(campaign=campaign, email='s1@example.com')

        out = send_campaign_continue.delay(str(campaign.id)).get()

        self.assertTrue(out['ok'])
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'sent')
        self.assertEqual(len(mail.outbox), 2)  # only the two unsent got mailed
        self.assertEqual(
            CampaignSend.objects.filter(campaign=campaign, kind='campaign', ok=True).count(), 4
        )
