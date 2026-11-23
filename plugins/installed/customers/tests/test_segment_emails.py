"""CUSTOMER_SEGMENT_EMAILS: the customers app answers who is in an RFM segment.

The newsletter narrows a campaign's confirmed list with it (C2), without
importing this app.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from morpheus.core import MorpheusEvents
from plugins.installed.customers.models import CustomerSegment

User = get_user_model()


def _filter(segment):
    from core.hooks import hook_registry

    return hook_registry.filter(MorpheusEvents.CUSTOMER_SEGMENT_EMAILS, None, segment=segment)


class SegmentEmailsTests(TestCase):
    def setUp(self):
        ann = User.objects.create_user(username='ann', email='Ann@Example.com', password='x')
        bob = User.objects.create_user(username='bob', email='bob@example.com', password='x')
        nobody = User.objects.create_user(username='nobody', email='', password='x')
        CustomerSegment.objects.create(customer=ann, segment='at_risk')
        CustomerSegment.objects.create(customer=bob, segment='loyal')
        CustomerSegment.objects.create(customer=nobody, segment='at_risk')

    def test_answers_lowercased_emails_of_the_segment(self):
        self.assertEqual(_filter('at_risk'), {'ann@example.com'})

    def test_unknown_segment_answers_empty_set(self):
        self.assertEqual(_filter('nope'), set())

    def test_campaign_audience_defaults_to_everyone(self):
        from plugins.installed.marketing.models import EmailCampaign

        c = EmailCampaign.objects.create(name='x', subject='y', html_body='<p>z</p>')
        self.assertEqual(c.audience, '')
