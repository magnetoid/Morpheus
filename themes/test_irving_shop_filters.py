"""Irving's shop: filters in one row above a four-column grid (owner, 2026-10-11).

The owner asked for the left sidebar to go, four products a row, and the
dropdowns above the products as filters; search already lives in the top bar.
The filters stay ONE form, so a filter with no control of its own (a search
query, a tag) has to ride along as a hidden field, or changing the category
would silently drop it.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from themes.test_head_contract import _activate_theme


class IrvingShopFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Product

        water = Category.objects.create(name='Water', slug='water', is_active=True)
        Category.objects.create(name='Light', slug='light', is_active=True)
        Product.objects.create(
            name='Folding Water Carrier',
            slug='folding-water-carrier',
            sku='IRV-WATER-1',
            price=Money(Decimal('12.00'), 'USD'),
            status='active',
            category=water,
        )

    def setUp(self):
        _activate_theme(self, 'irving_survival')

    def _page(self, query: str = '') -> str:
        resp = self.client.get(f'/products/{query}')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def _form(self, html: str) -> str:
        start = html.index('id="plp-filters"')
        return html[start : html.index('</form>', start)]

    def test_the_filters_sit_above_the_grid_with_no_sidebar(self):
        html = self._page()
        self.assertNotIn('plp-side', html)
        self.assertLess(html.index('id="plp-filters"'), html.index('class="grid-books"'))
        form = self._form(html)
        self.assertIn('id="plp-category"', form)
        self.assertIn('id="plp-sort"', form)

    def test_the_grid_shows_four_products_a_row_on_desktop(self):
        html = self._page()
        self.assertIn(
            '@media (min-width: 1024px) { .plp-main .grid-books '
            '{ grid-template-columns: repeat(4, minmax(0, 1fr)); } }',
            html,
        )

    def test_search_is_left_to_the_top_bar(self):
        form = self._form(self._page())
        self.assertNotIn('name="q"', form)

    def test_an_active_search_and_price_ride_along_with_the_filters(self):
        form = self._form(self._page('?q=carrier&price_min=5'))
        self.assertIn('<input type="hidden" name="q" value="carrier">', form)
        self.assertIn('<input type="hidden" name="price_min" value="5">', form)

    def test_the_default_order_is_named_for_what_it_is(self):
        form = self._form(self._page())
        self.assertIn('<option value="for_you" selected>', form)
