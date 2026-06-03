"""The vendor account-nav tile is contributed + safe for anonymous users."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase

from plugins.installed.marketplace.plugin import MarketplacePlugin
from plugins.installed.marketplace.templatetags.marketplace_account import vendor_for


class VendorAccountTileTests(SimpleTestCase):
    def test_contributes_account_nav_block(self):
        slots = {b.slot for b in MarketplacePlugin().contribute_storefront_blocks()}
        self.assertIn('account_nav', slots)

    def test_vendor_for_anonymous_is_none(self):
        self.assertIsNone(vendor_for(AnonymousUser()))
        self.assertIsNone(vendor_for(None))
