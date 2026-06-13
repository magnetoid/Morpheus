"""Affiliate end-user: social share buttons + leaderboard."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase


def _approved_affiliate(username='aff', handle='me'):
    from plugins.installed.affiliates.models import Affiliate, AffiliateProgram

    u = get_user_model().objects.create_user(
        username=username, email=f'{username}@x.test', password='pw'
    )
    prog, _ = AffiliateProgram.objects.get_or_create(slug='default', defaults={'name': 'Default'})
    aff = Affiliate.objects.create(program=prog, user=u, handle=handle, status='approved')
    return u, aff


class AffiliateLeaderboardTests(TestCase):
    def setUp(self):
        self.user, self.aff = _approved_affiliate()
        self.client.force_login(self.user)

    def test_leaderboard_renders(self):
        r = self.client.get('/affiliates/me/leaderboard/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Leaderboard')
        self.assertContains(r, '0 sale')  # my_sales == 0, empty board

    def test_links_page_has_leaderboard_link(self):
        r = self.client.get('/affiliates/me/links/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '/affiliates/me/leaderboard/')

    def test_share_buttons_render_for_a_link(self):
        from plugins.installed.affiliates.models import AffiliateLink

        AffiliateLink.objects.create(affiliate=self.aff)
        r = self.client.get('/affiliates/me/links/')
        self.assertContains(r, 'aff-share')
        self.assertContains(r, 'twitter.com/intent')
        self.assertContains(r, 'wa.me')

    def test_leaderboard_redirects_without_approved_affiliate(self):
        u2 = get_user_model().objects.create_user(
            username='nobody', email='n@x.test', password='pw'
        )
        self.client.force_login(u2)
        r = self.client.get('/affiliates/me/leaderboard/')
        self.assertEqual(r.status_code, 302)  # → apply
