"""Irving's home stage shows the two lead products side by side, under the copy.

The owner's ask (2026-10-10): the panel below the hero text — which showed one
product — carries two. A lone product with artwork keeps the full width; a
shop with no product artwork keeps the household-kit list.
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from themes.registry import theme_registry


def _product(name: str, slug: str, *, image: bool = True) -> dict:
    return {
        'id': str(uuid4()),
        'name': name,
        'slug': slug,
        'productType': 'simple',
        'shortDescription': f'{name}, for the household.',
        'category': {'name': 'Water', 'slug': 'water'},
        'price': {'amount': '29.00', 'currency': 'GBP'},
        'priceStartsFrom': False,
        'primaryImage': {'url': f'https://example.com/{slug}.jpg', 'altText': name}
        if image
        else None,
        'isOnSale': False,
        'discountPercentage': 0,
    }


def _home(products: list[dict]) -> dict:
    return {'featuredProducts': products, 'collections': [], 'categories': []}


class IrvingHomeStageTests(TestCase):
    def setUp(self):
        override = override_settings(MORPHEUS_ACTIVE_THEME='irving_survival')
        override.enable()
        self.addCleanup(override.disable)
        previous = theme_registry._active_name
        theme_registry.set_active('irving_survival')
        self.addCleanup(setattr, theme_registry, '_active_name', previous)
        cache.clear()
        self.addCleanup(cache.clear)

    def _render(self, products: list[dict]) -> str:
        with (
            patch(
                'plugins.installed.personalisation.services.rank_for_visitor',
                side_effect=lambda request, products, surface: products,
            ),
            patch(
                'plugins.installed.storefront.views.home.internal_graphql',
                return_value=_home(products),
            ),
        ):
            response = Client().get('/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_two_products_sit_side_by_side_under_the_copy(self):
        body = self._render(
            [_product('Water filter', 'water-filter'), _product('Wind-up torch', 'torch')]
        )
        stage = body.split('class="h-stage"', 1)[1].split('class="h-stats"', 1)[0]
        self.assertIn('h-stage__pair', stage)
        self.assertEqual(stage.count('class="h-panel"'), 2)
        self.assertIn('/products/water-filter/', stage)
        self.assertIn('/products/torch/', stage)
        # The hero copy comes first; the stage follows it directly.
        self.assertLess(body.index('Your needs don'), body.index('class="h-stage__pair"'))

    def test_a_lone_product_still_fills_the_stage(self):
        body = self._render([_product('Water filter', 'water-filter')])
        stage = body.split('class="h-stage"', 1)[1].split('class="h-stats"', 1)[0]
        self.assertEqual(stage.count('class="h-panel"'), 1)
        self.assertIn('h-stage__pair', stage)

    def test_no_artwork_keeps_the_household_kit_list(self):
        body = self._render([_product('Water filter', 'water-filter', image=False)])
        stage = body.split('class="h-stage"', 1)[1].split('class="h-stats"', 1)[0]
        self.assertNotIn('class="h-panel"', stage)
        self.assertIn('h-kit__list', stage)
