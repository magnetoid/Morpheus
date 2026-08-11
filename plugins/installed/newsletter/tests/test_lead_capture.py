"""A newsletter signup should become a CRM lead.

The storefront had a `newsletter_subscribe` view that did exactly that — but
the newsletter plugin owns the same URL and registers earlier, so the storefront
view never ran and the lead was never created. Moving the capture onto the
NEWSLETTER_SUBSCRIBED event makes it work regardless of which route wins, and
lets it disappear cleanly when crm is disabled.
"""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.crm.models import Lead
from plugins.installed.newsletter.services import subscribe
from plugins.registry import app_registry


class NewsletterLeadCaptureTests(TestCase):
    def test_signup_creates_a_lead(self):
        subscribe('reader@example.com', source='footer')
        lead = Lead.objects.filter(email='reader@example.com').first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.source, 'newsletter')

    def test_repeat_signup_does_not_duplicate_the_lead(self):
        subscribe('reader@example.com', source='footer')
        subscribe('reader@example.com', source='popup')
        self.assertEqual(Lead.objects.filter(email='reader@example.com').count(), 1)

    def test_invalid_email_creates_nothing(self):
        subscribe('not-an-email', source='footer')
        self.assertEqual(Lead.objects.count(), 0)

    def test_capture_stops_when_crm_is_disabled(self):
        # Bus-gated: a disabled plugin's subscriber does not run.
        app_registry.deactivate('crm')
        try:
            subscribe('offcrm@example.com', source='footer')
            self.assertFalse(Lead.objects.filter(email='offcrm@example.com').exists())
        finally:
            app_registry.activate('crm')

    def test_signup_still_succeeds_if_lead_capture_fails(self):
        from unittest.mock import patch

        from plugins.installed.newsletter.models import NewsletterSubscriber

        with patch(
            'plugins.installed.crm.services.upsert_lead', side_effect=RuntimeError('crm down')
        ):
            sub, _ = subscribe('resilient@example.com', source='footer')
        self.assertIsNotNone(sub)
        self.assertTrue(NewsletterSubscriber.objects.filter(email='resilient@example.com').exists())
