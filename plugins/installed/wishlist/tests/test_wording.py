"""Wishlist's pages speak for any shop (owner, 2026-10-23), in every language a store serves.

They carried the bookshop's words ("No saved books yet", "Browse the shelf", "A reading
list, shared.") on every store but the one that overrides the wishlist page. A page is
checked for the new phrases, and the templates for the old ones: the test theme's own copy
(dot_books) rightly says "Browse the shelf" around the page.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.template import engines
from django.templatetags.i18n import TranslateNode
from django.test import SimpleTestCase, TestCase
from django.utils.translation import trans_real
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.wishlist.services import add_item, get_or_create_wishlist, make_shareable

TEMPLATES = Path(__file__).resolve().parents[1] / 'templates' / 'wishlist'
BROWSER = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 Safari/605.1.15'


class WishlistWordingTests(TestCase):
    def test_an_empty_wishlist_speaks_for_any_shop(self):
        body = self.client.get('/wishlist/', HTTP_USER_AGENT=BROWSER, follow=True).content.decode()
        self.assertIn('Nothing saved yet.', body)
        self.assertIn('Browse the shop', body)
        template = (TEMPLATES / 'wishlist.html').read_text()
        self.assertNotIn('No saved books yet.', template)
        self.assertNotIn('Browse the shelf', template)

    def test_a_shared_wishlist_speaks_for_any_shop(self):
        user = get_user_model().objects.create_user(
            username='w@example.com', email='w@example.com', password='x'
        )
        product = Product.objects.create(
            name='Lamp', slug='lamp', sku='L1', status='active', price=Money(Decimal('10'), 'USD')
        )
        wishlist = get_or_create_wishlist(customer=user)
        add_item(wishlist=wishlist, product=product)
        url = f'/wishlist/shared/{make_shareable(wishlist)}/'
        body = self.client.get(url, HTTP_USER_AGENT=BROWSER, follow=True).content.decode()
        self.assertIn('Shared with you.', body)
        self.assertNotIn('A reading list, shared.', (TEMPLATES / 'shared.html').read_text())


class WishlistTranslationTests(SimpleTestCase):
    """Montenegro serves /sr/ and renders the shared page and the product-page button."""

    def test_every_string_is_marked_and_has_a_serbian_translation(self):
        catalog = trans_real.translation('sr')._catalog
        engine = engines['django'].engine
        msgids = [
            str(node.filter_expression.var.literal).replace('%', '%%')
            for path in sorted(TEMPLATES.rglob('*.html'))
            for node in engine.from_string(path.read_text()).nodelist.get_nodes_by_type(
                TranslateNode
            )
        ]
        self.assertGreaterEqual(len(msgids), 8)
        self.assertEqual([m for m in msgids if m not in catalog], [])
