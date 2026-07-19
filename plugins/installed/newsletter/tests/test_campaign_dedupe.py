"""Regression — campaign dedupe/count filter on ``kind='campaign', ok=True``.

Guards Fix 9+19: ``send_campaign``'s ``already`` set and ``recipient_count``
once filtered ``campaign=campaign`` alone, which (a) stranded a FAILED
(``ok=False``) recipient as permanently un-retryable, (b) let a ``kind='test'``
row for a confirmed subscriber suppress the real campaign, and (c) inflated
``recipient_count`` with test rows. Both queries now pin ``kind='campaign',
ok=True``.

Under tests CELERY_TASK_ALWAYS_EAGER is on, so ``send_campaign.delay`` and the
inner ``deliver_email.delay`` run inline and land in ``mail.outbox`` — no real
email fires (mirrors ``test_campaign_send``).
"""

from __future__ import annotations

from django.test import TestCase, override_settings

from plugins.installed.marketing.models import EmailCampaign
from plugins.installed.newsletter.models import CampaignSend, NewsletterSubscriber
from plugins.installed.newsletter.tasks import send_campaign


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


def _recipients(outbox) -> set[str]:
    return {addr for msg in outbox for addr in msg.to}


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class CampaignDedupeTests(TestCase):
    def test_failed_row_is_retried(self):
        # A confirmed subscriber with a pre-existing ok=False row must be
        # re-attempted on a re-run — the old bug skipped them forever.
        from django.core import mail

        campaign = _campaign()
        NewsletterSubscriber.objects.create(email='x@example.com', status='confirmed')
        CampaignSend.objects.create(
            campaign=campaign, email='x@example.com', ok=False, detail='smtp boom'
        )

        out = send_campaign.delay(str(campaign.id)).get()

        self.assertTrue(out['ok'])
        self.assertEqual(out['sent'], 1)  # retried, not skipped
        self.assertEqual(out['skipped'], 0)
        self.assertIn('x@example.com', _recipients(mail.outbox))
        # a fresh ok=True campaign row now exists for X
        self.assertTrue(
            CampaignSend.objects.filter(
                campaign=campaign, email='x@example.com', kind='campaign', ok=True
            ).exists()
        )

    def test_test_row_does_not_suppress_real_send(self):
        # A kind='test' row (as send_campaign_test logs) for a confirmed
        # subscriber must NOT block the real campaign to that address.
        from django.core import mail

        campaign = _campaign()
        NewsletterSubscriber.objects.create(email='y@example.com', status='confirmed')
        CampaignSend.objects.create(campaign=campaign, email='y@example.com', kind='test', ok=True)

        out = send_campaign.delay(str(campaign.id)).get()

        self.assertTrue(out['ok'])
        self.assertEqual(out['sent'], 1)
        self.assertEqual(out['skipped'], 0)
        self.assertIn('y@example.com', _recipients(mail.outbox))
        self.assertTrue(
            CampaignSend.objects.filter(
                campaign=campaign, email='y@example.com', kind='campaign', ok=True
            ).exists()
        )

    def test_recipient_count_excludes_test_rows(self):
        # recipient_count counts only kind='campaign', ok=True — a test row for
        # the same recipient must not inflate it.
        campaign = _campaign()
        NewsletterSubscriber.objects.create(email='z@example.com', status='confirmed')
        CampaignSend.objects.create(campaign=campaign, email='z@example.com', kind='test', ok=True)

        send_campaign.delay(str(campaign.id)).get()

        campaign.refresh_from_db()
        self.assertEqual(campaign.recipient_count, 1)
        # there ARE two ledger rows (1 test + 1 campaign); the count ignored the test one
        self.assertEqual(CampaignSend.objects.filter(campaign=campaign).count(), 2)
        self.assertEqual(
            CampaignSend.objects.filter(campaign=campaign, kind='campaign', ok=True).count(), 1
        )
