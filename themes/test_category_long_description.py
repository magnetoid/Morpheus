"""Every theme shows a category's long description below its products.

The short description stays the intro above the grid; the long one is the guide a
shopper scrolls to after browsing. A field the store can fill but no theme shows
would be a control that does nothing (CLAUDE.md), so every shipped theme renders it.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from themes.test_head_contract import _activate_theme

GUIDE = '<h2>How much water to keep</h2><p>Plan four liters per person per day.</p>'


class CategoryLongDescriptionThemeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Product

        water = Category.objects.create(
            name='Water', slug='water', description='Filters and storage.', long_description=GUIDE
        )
        Category.objects.create(name='Light', slug='light', description='Lamps.')
        Product.objects.create(
            name='Folding Water Carrier',
            slug='folding-water-carrier',
            sku='IRV-WATER-1',
            price=Money(Decimal('12.00'), 'USD'),
            status='active',
            category=water,
        )

    def _page(self, theme: str, slug: str) -> str:
        _activate_theme(self, theme)
        resp = self.client.get(f'/category/{slug}/')
        self.assertEqual(resp.status_code, 200, theme)
        return resp.content.decode()

    def test_every_theme_shows_it_below_the_products(self):
        for theme in ('irving_survival', 'dot_books', 'supernatural_shop'):
            with self.subTest(theme=theme):
                html = self._page(theme, 'water')
                self.assertIn('<h2>How much water to keep</h2>', html)
                self.assertLess(
                    html.index('folding-water-carrier'), html.index('How much water to keep')
                )

    def test_a_category_without_one_shows_no_empty_section(self):
        html = self._page('irving_survival', 'light')
        self.assertNotIn('<section class="category-guide"', html)
