"""Affiliate personal coupon codes — handle-derived, unique, attribution-only."""

# ruff: noqa: PLC0415
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase


def _approved_affiliate(username='cp', handle='jane'):
    from plugins.installed.affiliates.models import Affiliate, AffiliateProgram

    u = get_user_model().objects.create_user(
        username=username, email=f'{username}@x.test', password='pw'
    )
    prog, _ = AffiliateProgram.objects.get_or_create(slug='default', defaults={'name': 'Default'})
    aff = Affiliate.objects.create(program=prog, user=u, handle=handle, status='approved')
    return u, aff


class AffiliateCouponTests(TestCase):
    def setUp(self):
        self.user, self.aff = _approved_affiliate(handle='jane')
        self.client.force_login(self.user)

    def test_unclaimed_shows_claim_button(self):
        r = self.client.get('/affiliates/me/coupon/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Claim my coupon code')

    def test_claim_generates_handle_derived_code(self):
        from plugins.installed.affiliates.services import affiliate_coupon

        r = self.client.post('/affiliates/me/coupon/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(affiliate_coupon(self.aff), 'JANE')

    def test_page_shows_code_after_claim(self):
        from plugins.installed.affiliates.services import affiliate_coupon

        affiliate_coupon(self.aff, claim=True)
        r = self.client.get('/affiliates/me/coupon/')
        self.assertContains(r, 'JANE')

    def test_unique_suffix_on_collision(self):
        from plugins.installed.affiliates.models import AffiliateLink
        from plugins.installed.affiliates.services import affiliate_coupon

        # Someone already holds 'JANE' → this affiliate gets JANE2.
        other_u, other = _approved_affiliate(username='ot', handle='other')
        AffiliateLink.objects.create(affiliate=other, coupon_code='JANE')
        self.assertEqual(affiliate_coupon(self.aff, claim=True), 'JANE2')

    def test_idempotent(self):
        from plugins.installed.affiliates.services import affiliate_coupon

        first = affiliate_coupon(self.aff, claim=True)
        second = affiliate_coupon(self.aff, claim=True)
        self.assertEqual(first, second)  # claiming again returns the same code
