"""Phase 3 — the campaign send path, win-back, and one-click unsubscribe.

Under tests CELERY_TASK_ALWAYS_EAGER is on, so ``send_campaign.delay`` and the
inner ``deliver_email.delay`` run inline and land in ``mail.outbox`` — these
tests exercise the real task bodies, not mocks.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings

from plugins.installed.marketing.models import EmailCampaign
from plugins.installed.newsletter.models import CampaignSend, NewsletterSubscriber
from plugins.installed.newsletter.tasks import send_campaign, send_campaign_test, send_winback

User = get_user_model()


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
class CampaignSendTests(TestCase):
    def setUp(self):
        self.confirmed = NewsletterSubscriber.objects.create(
            email='reader@example.com', status='confirmed'
        )
        NewsletterSubscriber.objects.create(email='pending@example.com', status='pending')
        NewsletterSubscriber.objects.create(email='gone@example.com', status='unsubscribed')

    def test_sends_to_confirmed_only_with_rfc8058_headers(self):
        campaign = _campaign()
        out = send_campaign.delay(str(campaign.id)).get()
        self.assertTrue(out['ok'])
        self.assertEqual(out['sent'], 1)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['reader@example.com'])
        # RFC 8058 one-click pair, per recipient
        self.assertIn(self.confirmed.confirm_token, msg.extra_headers['List-Unsubscribe'])
        self.assertEqual(msg.extra_headers['List-Unsubscribe-Post'], 'List-Unsubscribe=One-Click')
        # visible unsubscribe footer in the body
        self.assertIn('Unsubscribe:', msg.body)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'sent')
        self.assertEqual(campaign.recipient_count, 1)
        self.assertIsNotNone(campaign.sent_at)

    def test_rerun_is_noop(self):
        campaign = _campaign()
        send_campaign.delay(str(campaign.id)).get()
        out = send_campaign.delay(str(campaign.id)).get()
        self.assertFalse(out['ok'])  # status guard: already sent
        self.assertEqual(len(mail.outbox), 1)

    def test_already_sending_is_not_reblasted(self):
        # A campaign another worker is mid-send on (status='sending') must not be
        # blasted again — the guard + atomic claim prevent a duplicate send.
        campaign = _campaign(status='sending')
        out = send_campaign.delay(str(campaign.id)).get()
        self.assertFalse(out['ok'])
        self.assertEqual(len(mail.outbox), 0)

    def test_ledger_skips_already_sent_recipient(self):
        campaign = _campaign()
        CampaignSend.objects.create(campaign=campaign, email='reader@example.com')
        out = send_campaign.delay(str(campaign.id)).get()
        self.assertTrue(out['ok'])
        self.assertEqual(out['sent'], 0)
        self.assertEqual(out['skipped'], 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_test_send_changes_nothing(self):
        campaign = _campaign()
        out = send_campaign_test.delay(str(campaign.id), 'me@example.com').get()
        self.assertTrue(out['ok'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('[test]', mail.outbox[0].subject)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'draft')  # untouched
        self.assertTrue(CampaignSend.objects.filter(kind='test', campaign=campaign).exists())


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class OneClickUnsubscribeTests(TestCase):
    def test_post_unsubscribes_without_csrf(self):
        sub = NewsletterSubscriber.objects.create(email='bye@example.com', status='confirmed')
        resp = Client(enforce_csrf_checks=True).post(
            f'/newsletter/unsubscribe/{sub.confirm_token}/'
        )
        self.assertEqual(resp.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'unsubscribed')


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class WinbackTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='lapsed', email='lapsed@example.com', password='x', first_name='Mara'
        )

    def test_winback_requires_confirmed_subscription(self):
        self.assertFalse(send_winback(self.user))  # no subscription → never email
        self.assertEqual(len(mail.outbox), 0)

    def test_winback_sends_once_with_headers(self):
        NewsletterSubscriber.objects.create(email='lapsed@example.com', status='confirmed')
        self.assertTrue(send_winback(self.user))
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn('List-Unsubscribe', msg.extra_headers)
        # dedupe window: a second nightly flip inside 30 days stays silent
        self.assertFalse(send_winback(self.user))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(CampaignSend.objects.filter(kind='winback').count(), 1)

    def test_hook_fires_winback_on_at_risk_flip(self):
        from morpheus.core import MorpheusEvents, hook_registry

        NewsletterSubscriber.objects.create(email='lapsed@example.com', status='confirmed')
        hook_registry.fire(
            MorpheusEvents.CUSTOMER_SEGMENT_CHANGED,
            customer=self.user,
            old='loyal',
            new='at_risk',
        )
        self.assertEqual(len(mail.outbox), 1)
