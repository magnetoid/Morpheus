"""Supernatural's product cards and home page (owner, 2026-10-19).

Every card names its category and gives two lines of the product's short
description, on the shop's grids and in the home page's carousels (the rail
used to hide the description). The home page puts content between three groups
of carousels instead of stacking eight of them: an icon strip of the shop's
standards, the guides, the standards band, and the shelves last.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from djmoney.money import Money

from themes.test_head_contract import _activate_theme

_BASE = Path(__file__).parent / 'library/supernatural_shop/templates/storefront/base.html'
_GUIDE = {
    'title': 'A simple daily stack',
    'slug': 'a-simple-daily-stack',
    'excerpt': 'Three things, taken every day.',
    'date_label': 'October 9, 2026 · 3 min read',
}


class SupernaturalCardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Product

        shelf = Category.objects.create(name='Daily staples', slug='wellness-vitamins')
        Product.objects.create(
            name='Magnesium Glycinate',
            slug='magnesium-glycinate',
            sku='MG-1',
            price=Money(Decimal('24.00'), 'USD'),
            status='active',
            category=shelf,
            short_description='<p>Gentle on the stomach. Taken at night.</p>',
        )

    def setUp(self):
        _activate_theme(self, 'supernatural_shop')

    def _card(self, html, slug):
        start = html.index(f'href="/products/{slug}/"')
        end = html.find('data-product-card', start)
        return html[start : end if end != -1 else start + 4000]

    def test_a_card_names_its_category_and_describes_the_product(self):
        card = self._card(self.client.get('/products/').content.decode(), 'magnesium-glycinate')
        self.assertIn('<p class="book__category">Daily staples</p>', card)
        self.assertIn('Gentle on the stomach.', card)

    def test_a_carousel_card_keeps_its_description(self):
        self.assertNotIn('.grid-books--rail .book__excerpt { display: none; }', _BASE.read_text())

    def test_text_is_a_little_larger(self):
        css = _BASE.read_text()
        self.assertIn('html { font-size: 106.25%;', css)
        self.assertIn('font-size: 17px;', css)


class SupernaturalHomeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Product
        from plugins.installed.dynamics.models import DynamicBlock

        shelf = Category.objects.create(name='Pantry', slug='wellness-superfoods')
        Product.objects.create(
            name='Ground Flax',
            slug='ground-flax',
            sku='GF-1',
            price=Money(Decimal('9.00'), 'USD'),
            status='active',
            category=shelf,
        )
        for heading, slot in (
            ('Rail one', 'home_after_rails'),
            ('Rail two', 'home_above_grid'),
            ('Rail three', 'home_below_grid'),
        ):
            block = DynamicBlock.objects.create(
                name=heading, heading=heading, slot=slot, strategy='manual', limit=4
            )
            block.categories.set([shelf])

    def setUp(self):
        _activate_theme(self, 'supernatural_shop')

    def test_content_sits_between_the_groups_of_carousels(self):
        with patch('plugins.installed.cms.services.list_journal_entries', return_value=[_GUIDE]):
            html = self.client.get('/').content.decode()
        order = [
            'data-home-strip',
            '>Rail one<',
            'data-home-guides',
            '>Rail two<',
            'data-home-standards',
            '>Rail three<',
            'data-home-shelves',
        ]
        positions = [html.find(marker) for marker in order]
        self.assertNotIn(-1, positions, dict(zip(order, positions, strict=True)))
        self.assertEqual(positions, sorted(positions))

    def test_the_guides_are_numbered(self):
        with patch('plugins.installed.cms.services.list_journal_entries', return_value=[_GUIDE]):
            html = self.client.get('/').content.decode()
        guides = html[html.index('data-home-guides') :]
        self.assertIn('<span class="guide-card__no" aria-hidden="true">01</span>', guides)
