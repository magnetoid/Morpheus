"""Send campaigns points nowhere else, and Marketing has one Campaigns tab."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from plugins.installed.admin_dashboard import navigation

_GONE = '/dashboard/apps/marketing/campaigns/'


class CampaignsPageLinkTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='camp-owner',
            email='camp@example.test',
            password='x',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_send_campaigns_has_no_link_to_the_marketing_copy(self):
        resp = self.client.get('/dashboard/newsletter/campaigns/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertNotIn(_GONE, html)
        self.assertIn('No campaigns yet.', html)

    def test_the_marketing_copy_is_gone(self):
        self.assertEqual(self.client.get(_GONE).status_code, 404)

    def test_marketing_lists_one_campaigns_entry_and_it_is_newsletters(self):
        request = RequestFactory().get('/dashboard/marketing/coupons/')
        request.user = self.user
        entries = [
            t
            for t in navigation.tabs(self.user)
            if t.section == 'marketing' and t.label == 'Campaigns'
        ]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].plugin, 'newsletter')
        self.assertEqual(entries[0].url, '/dashboard/newsletter/campaigns/')
