"""C2 — a campaign is sanitised, wrapped in the store layout and sent per audience."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from morpheus.core import MorpheusEvents
from plugins.installed.customers.models import CustomerSegment
from plugins.installed.marketing.models import EmailCampaign
from plugins.installed.newsletter.models import NewsletterSubscriber
from plugins.installed.newsletter.tasks import send_campaign, send_campaign_test

User = get_user_model()
LAYOUT_MARKER = 'class="preheader"'


def _campaign(**kw):
    defaults = {'name': 'Picks', 'subject': 'Five picks', 'html_body': '<p>Hi</p>'}
    defaults.update(kw)
    return EmailCampaign.objects.create(**defaults)


def _html(msg) -> str:
    return next(body for body, kind in msg.alternatives if kind == 'text/html')


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
)
class CampaignRenderTests(TestCase):
    def test_body_is_sanitised_and_wrapped_in_the_store_layout(self):
        NewsletterSubscriber.objects.create(email='r@example.com', status='confirmed')
        c = _campaign(html_body='<p>Hi</p><script>x()</script><img src=x onerror=y()>')
        send_campaign.delay(str(c.id)).get()
        html = _html(mail.outbox[0])
        self.assertNotIn('<script', html)
        self.assertNotIn('onerror', html)
        self.assertIn('<p>Hi</p>', html)
        self.assertIn(LAYOUT_MARKER, html)

    def test_each_recipient_gets_their_own_unsubscribe_link(self):
        from plugins.installed.newsletter.campaigns import UNSUBSCRIBE_SENTINEL

        one = NewsletterSubscriber.objects.create(email='one@example.com', status='confirmed')
        two = NewsletterSubscriber.objects.create(email='two@example.com', status='confirmed')
        send_campaign.delay(str(_campaign().id)).get()
        self.assertEqual(len(mail.outbox), 2)
        for msg in mail.outbox:
            mine, other = (one, two) if msg.to == ['one@example.com'] else (two, one)
            for part in (msg.body, _html(msg)):
                self.assertIn(mine.confirm_token, part)
                self.assertNotIn(other.confirm_token, part)
                self.assertNotIn(UNSUBSCRIBE_SENTINEL, part)

    def test_segment_audience_narrows_the_confirmed_list(self):
        NewsletterSubscriber.objects.create(email='a@x.com', status='confirmed')
        NewsletterSubscriber.objects.create(email='b@x.com', status='confirmed')
        NewsletterSubscriber.objects.create(email='c@x.com', status='pending')
        for name, email in (('a', 'A@X.com'), ('c', 'c@x.com')):
            user = User.objects.create_user(username=name, email=email, password='x')
            CustomerSegment.objects.create(customer=user, segment='loyal')
        c = _campaign(audience='loyal')
        send_campaign.delay(str(c.id)).get()
        self.assertEqual([m.to for m in mail.outbox], [['a@x.com']])
        c.refresh_from_db()
        self.assertEqual(c.recipient_count, 1)

    def test_segment_match_ignores_the_subscribers_case_too(self):
        NewsletterSubscriber.objects.create(email='Reader@Example.com', status='confirmed')
        user = User.objects.create_user(username='r', email='reader@example.com', password='x')
        CustomerSegment.objects.create(customer=user, segment='loyal')
        send_campaign.delay(str(_campaign(audience='loyal').id)).get()
        self.assertEqual([m.to for m in mail.outbox], [['Reader@Example.com']])

    def test_relative_links_become_absolute(self):
        from core.utils.site import site_base_url

        NewsletterSubscriber.objects.create(email='r@example.com', status='confirmed')
        body = '<p><a href="/products/x/">Book</a> <a href="https://a.example/">A</a></p>'
        send_campaign.delay(str(_campaign(html_body=body).id)).get()
        html = _html(mail.outbox[0])
        self.assertIn(f'href="{site_base_url()}products/x/"', html)
        self.assertIn('href="https://a.example/"', html)

    def test_segment_audience_refused_when_nobody_answers(self):
        from core.hooks import hook_registry
        from plugins.installed.newsletter.campaigns import CampaignError, audience_emails

        event = MorpheusEvents.CUSTOMER_SEGMENT_EMAILS
        saved = list(hook_registry._handlers.get(event, []))
        hook_registry._handlers[event] = []
        self.addCleanup(hook_registry._handlers.__setitem__, event, saved)
        with self.assertRaises(CampaignError):
            audience_emails('loyal')

    def test_unknown_audience_is_refused(self):
        from plugins.installed.newsletter.campaigns import CampaignError, audience_emails

        with self.assertRaises(CampaignError):
            audience_emails('vips')

    def test_test_copy_uses_the_layout_and_a_sample_link(self):
        c = _campaign()
        send_campaign_test.delay(str(c.id), 'me@example.com').get()
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertTrue(msg.subject.startswith('[test] '))
        self.assertIn(LAYOUT_MARKER, _html(msg))
        self.assertNotIn('List-Unsubscribe', msg.extra_headers)
