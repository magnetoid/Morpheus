"""C2 — Linda lists, drafts and sends campaigns; both writes wait for the merchant's yes."""

from __future__ import annotations

import types
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from plugins.installed.marketing.models import EmailCampaign
from plugins.installed.newsletter.models import NewsletterSubscriber


def _tool(name):
    from core.agents.registry import agent_registry

    return agent_registry.get_tool(name)


class CampaignToolTests(TestCase):
    def test_tools_are_registered_with_approval_on_writes(self):
        cases = {
            'newsletter.campaigns': (['promotions.read'], False),
            'newsletter.campaign_create': (['promotions.write'], True),
            'newsletter.campaign_send': (['promotions.write'], True),
            'newsletter.campaign_cancel': (['promotions.write'], True),
        }
        for name, (scopes, approval) in cases.items():
            tool = _tool(name)
            self.assertIsNotNone(tool, name)
            self.assertEqual(list(tool.scopes), scopes, name)
            self.assertEqual(tool.requires_approval, approval, name)

    def test_create_makes_a_sanitised_draft(self):
        out = (
            _tool('newsletter.campaign_create')
            .invoke(
                {
                    'name': 'Gifts',
                    'subject': 'Gift ideas',
                    'body_html': '<p>Ideas</p><script>x</script>',
                    'audience': 'champions',
                }
            )
            .output
        )
        c = EmailCampaign.objects.get(pk=out['id'])
        self.assertEqual((out['status'], c.status, c.audience), ('draft', 'draft', 'champions'))
        self.assertNotIn('<script', c.html_body)

    def test_create_reports_a_refusal(self):
        out = (
            _tool('newsletter.campaign_create')
            .invoke({'name': 'x', 'subject': '', 'body_html': '<p>y</p>'})
            .output
        )
        self.assertIn('required', out['error'])
        self.assertFalse(EmailCampaign.objects.exists())

    def test_send_with_time_schedules(self):
        c = EmailCampaign.objects.create(name='a', subject='b', html_body='<p>c</p>')
        when = (timezone.now() + timedelta(days=1)).replace(microsecond=0)
        out = (
            _tool('newsletter.campaign_send')
            .invoke({'campaign_id': str(c.id), 'send_at': when.isoformat()})
            .output
        )
        c.refresh_from_db()
        self.assertEqual(
            (out['status'], c.status, c.scheduled_at), ('scheduled', 'scheduled', when)
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='shop@example.com',
    )
    def test_send_without_time_sends(self):
        NewsletterSubscriber.objects.create(email='r@example.com', status='confirmed')
        c = EmailCampaign.objects.create(name='a', subject='b', html_body='<p>c</p>')
        _tool('newsletter.campaign_send').invoke({'campaign_id': str(c.id)})
        self.assertEqual(len(mail.outbox), 1)

    def test_send_reports_queued_before_the_worker_claims_it(self):
        from unittest import mock

        from plugins.installed.newsletter.tasks import send_campaign

        c = EmailCampaign.objects.create(name='a', subject='b', html_body='<p>c</p>')
        with mock.patch.object(send_campaign, 'delay'):
            out = _tool('newsletter.campaign_send').invoke({'campaign_id': str(c.id)}).output
        self.assertEqual(out['status'], 'queued')

    def test_cancel_returns_a_scheduled_campaign_to_draft(self):
        c = EmailCampaign.objects.create(
            name='a',
            subject='b',
            html_body='<p>c</p>',
            status='scheduled',
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        out = _tool('newsletter.campaign_cancel').invoke({'campaign_id': str(c.id)}).output
        c.refresh_from_db()
        self.assertEqual((out['status'], c.status, c.scheduled_at), ('draft', 'draft', None))

    def test_cancel_refuses_a_draft(self):
        c = EmailCampaign.objects.create(name='a', subject='b', html_body='<p>c</p>')
        out = _tool('newsletter.campaign_cancel').invoke({'campaign_id': str(c.id)}).output
        self.assertIn('not scheduled', out['error'])

    def test_send_refuses_a_sent_campaign_with_a_message(self):
        c = EmailCampaign.objects.create(name='a', subject='b', html_body='<p>c</p>', status='sent')
        out = _tool('newsletter.campaign_send').invoke({'campaign_id': str(c.id)}).output
        self.assertIn('cannot be sent', out['error'])

    def test_send_refuses_a_time_without_an_offset(self):
        c = EmailCampaign.objects.create(name='a', subject='b', html_body='<p>c</p>')
        out = (
            _tool('newsletter.campaign_send')
            .invoke({'campaign_id': str(c.id), 'send_at': '2099-01-01T10:00'})
            .output
        )
        self.assertIn('error', out)
        c.refresh_from_db()
        self.assertEqual(c.status, 'draft')

    def test_list_shows_status_and_missed(self):
        EmailCampaign.objects.create(
            name='late',
            subject='b',
            html_body='<p>c</p>',
            scheduled_at=timezone.now() - timedelta(days=2),
        )
        rows = _tool('newsletter.campaigns').invoke({}).output['campaigns']
        self.assertEqual(rows[0]['name'], 'late')
        self.assertTrue(rows[0]['missed'])

    def test_tools_are_in_lindas_catalogue(self):
        from plugins.installed.agent_mcp.linda_turn import LindaTurn, catalogue

        user = types.SimpleNamespace(is_staff=True, is_superuser=True, pk=1)
        names = {
            t.name
            for t in catalogue(LindaTurn(user=user, conversation_key='user:1', mode_slug='general'))
        }
        for name in (
            'newsletter.campaigns',
            'newsletter.campaign_create',
            'newsletter.campaign_send',
        ):
            self.assertIn(name, names)
