"""Affiliate personal analytics dashboard."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase


def _approved_affiliate(username='an', handle='an'):
    from plugins.installed.affiliates.models import Affiliate, AffiliateProgram

    u = get_user_model().objects.create_user(
        username=username, email=f'{username}@x.test', password='pw'
    )
    prog, _ = AffiliateProgram.objects.get_or_create(slug='default', defaults={'name': 'Default'})
    aff = Affiliate.objects.create(program=prog, user=u, handle=handle, status='approved')
    return u, aff


class AffiliateAnalyticsTests(TestCase):
    def setUp(self):
        self.user, self.aff = _approved_affiliate()
        self.client.force_login(self.user)

    def test_renders_empty(self):
        r = self.client.get('/affiliates/me/analytics/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Analytics')
        self.assertContains(r, 'Per click')  # KPI label

    def test_shows_link_in_top_links(self):
        from plugins.installed.affiliates.models import AffiliateLink

        AffiliateLink.objects.create(
            affiliate=self.aff, label='Promo', click_count=12, conversion_count=3
        )
        r = self.client.get('/affiliates/me/analytics/')
        self.assertContains(r, 'Promo')
        self.assertContains(r, '12')  # clicks

    def test_links_header_has_analytics_link(self):
        r = self.client.get('/affiliates/me/links/')
        self.assertContains(r, '/affiliates/me/analytics/')
