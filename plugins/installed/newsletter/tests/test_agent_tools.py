"""Newsletter agent commands — Linda reads the list + manages popups."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.newsletter.agent_tools import (
    newsletter_create_popup_tool,
    newsletter_list_subscribers_tool,
    newsletter_stats_tool,
    newsletter_toggle_popup_tool,
)
from plugins.installed.newsletter.models import NewsletterSubscriber, SignupPopup
from plugins.installed.newsletter.plugin import NewsletterPlugin


class NewsletterAgentToolTests(TestCase):
    def test_plugin_contributes_four_tools(self):
        names = {t.name for t in NewsletterPlugin().contribute_agent_tools()}
        self.assertEqual(
            names,
            {
                'newsletter.stats',
                'newsletter.list_subscribers',
                'newsletter.create_popup',
                'newsletter.toggle_popup',
            },
        )

    def test_stats_counts_by_status(self):
        NewsletterSubscriber.objects.create(email='a@x.test', status='confirmed')
        NewsletterSubscriber.objects.create(email='b@x.test', status='pending')
        out = newsletter_stats_tool.invoke({}).output
        self.assertEqual(out['confirmed'], 1)
        self.assertEqual(out['pending'], 1)
        self.assertEqual(out['total'], 2)

    def test_list_filters_by_status(self):
        NewsletterSubscriber.objects.create(email='c@x.test', status='confirmed')
        NewsletterSubscriber.objects.create(email='d@x.test', status='pending')
        out = newsletter_list_subscribers_tool.invoke({'status': 'confirmed'}).output
        self.assertEqual(out['count'], 1)
        self.assertEqual(out['subscribers'][0]['email'], 'c@x.test')

    def test_create_popup_disabled_then_toggle(self):
        created = newsletter_create_popup_tool.invoke(
            {'name': 'Welcome', 'trigger': 'exit_intent'}
        ).output
        self.assertFalse(created['enabled'])
        popup = SignupPopup.objects.get(id=created['id'])
        self.assertEqual(popup.trigger, 'exit_intent')

        on = newsletter_toggle_popup_tool.invoke(
            {'popup_id': created['id'], 'enabled': True}
        ).output
        self.assertTrue(on['enabled'])

    def test_toggle_unknown_popup_errors(self):
        import uuid

        out = newsletter_toggle_popup_tool.invoke(
            {'popup_id': str(uuid.uuid4()), 'enabled': True}
        ).output
        self.assertIn('error', out)

    def test_scopes(self):
        self.assertEqual(newsletter_stats_tool.scopes, ['analytics.read'])
        self.assertEqual(newsletter_create_popup_tool.scopes, ['content.write'])
