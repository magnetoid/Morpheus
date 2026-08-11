"""Newsletter double-opt-in lifecycle + public endpoints."""

from __future__ import annotations

from django.core import mail
from django.test import Client, TestCase, override_settings

from plugins.installed.newsletter.app import NewsletterPlugin
from plugins.installed.newsletter.models import NewsletterSubscriber
from plugins.installed.newsletter.services import confirm, subscribe, unsubscribe


@override_settings(DEFAULT_FROM_EMAIL='store@example.test')
class OptInLifecycleTests(TestCase):
    def test_subscribe_creates_pending_and_sends_confirm(self):
        sub, created = subscribe('Hi@Example.test', source='popup')
        self.assertTrue(created)
        self.assertEqual(sub.email, 'hi@example.test')  # normalised
        self.assertEqual(sub.status, 'pending')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['hi@example.test'])

    def test_confirm_flips_to_confirmed_and_welcomes(self):
        sub, _ = subscribe('a@example.test')
        mail.outbox.clear()
        confirmed = confirm(sub.confirm_token)
        self.assertEqual(confirmed.status, 'confirmed')
        self.assertIsNotNone(confirmed.confirmed_at)
        self.assertEqual(len(mail.outbox), 1)  # welcome

    def test_confirm_is_idempotent(self):
        sub, _ = subscribe('b@example.test')
        confirm(sub.confirm_token)
        mail.outbox.clear()
        confirm(sub.confirm_token)  # second time
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'confirmed')
        self.assertEqual(len(mail.outbox), 0)  # no duplicate welcome

    def test_already_confirmed_subscribe_does_not_resend(self):
        sub, _ = subscribe('c@example.test')
        confirm(sub.confirm_token)
        mail.outbox.clear()
        subscribe('c@example.test')
        self.assertEqual(len(mail.outbox), 0)

    def test_unsubscribe_is_terminal(self):
        sub, _ = subscribe('d@example.test')
        confirm(sub.confirm_token)
        out = unsubscribe(sub.confirm_token)
        self.assertEqual(out.status, 'unsubscribed')
        self.assertIsNotNone(out.unsubscribed_at)

    def test_invalid_email_rejected(self):
        sub, created = subscribe('not-an-email')
        self.assertIsNone(sub)
        self.assertFalse(created)
        self.assertEqual(NewsletterSubscriber.objects.count(), 0)

    def test_confirm_unknown_token_is_none(self):
        self.assertIsNone(confirm('nope'))


class PluginContributionTests(TestCase):
    def test_contributes_email_templates(self):
        keys = {t.key for t in NewsletterPlugin().contribute_email_templates()}
        self.assertEqual(keys, {'newsletter_confirm', 'newsletter_welcome', 'newsletter_winback'})


@override_settings(DEFAULT_FROM_EMAIL='store@example.test')
class EndpointTests(TestCase):
    def test_subscribe_endpoint_returns_json(self):
        r = Client().post('/newsletter/subscribe/', {'email': 'e@example.test'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        self.assertTrue(
            NewsletterSubscriber.objects.filter(email='e@example.test', status='pending').exists()
        )

    def test_subscribe_endpoint_rejects_bad_email(self):
        r = Client().post('/newsletter/subscribe/', {'email': 'x'})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()['ok'])

    def test_confirm_endpoint(self):
        sub, _ = subscribe('f@example.test')
        r = Client().get(f'/newsletter/confirm/{sub.confirm_token}/')
        self.assertEqual(r.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'confirmed')
