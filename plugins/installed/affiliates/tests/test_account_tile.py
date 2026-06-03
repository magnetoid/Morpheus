"""The affiliate account-nav tile is contributed + safe for anonymous users."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase

from plugins.installed.affiliates.plugin import AffiliatesPlugin
from plugins.installed.affiliates.templatetags.affiliates_account import affiliate_for


class AffiliateAccountTileTests(SimpleTestCase):
    def test_contributes_account_nav_block(self):
        slots = {b.slot for b in AffiliatesPlugin().contribute_storefront_blocks()}
        self.assertIn('account_nav', slots)

    def test_affiliate_for_anonymous_is_none(self):
        self.assertIsNone(affiliate_for(AnonymousUser()))
        self.assertIsNone(affiliate_for(None))
