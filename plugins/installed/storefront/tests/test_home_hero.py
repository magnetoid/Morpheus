"""Homepage hero regression tests."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from plugins.installed.storefront.views.home import home


def _hero_product(name: str, slug: str) -> dict:
    return {
        'id': str(uuid4()),
        'name': name,
        'slug': slug,
        'productType': 'simple',
        'shortDescription': f'{name} is the featured recommendation for the rotating homepage shelf.',
        'category': {'name': 'Fiction', 'slug': 'fiction'},
        'price': {'amount': '19.00', 'currency': 'USD'},
        'priceStartsFrom': False,
        'primaryImage': {
            'url': f'https://example.com/{slug}.jpg',
            'altText': f'{name} cover',
        },
        'isOnSale': False,
        'discountPercentage': 0,
    }


def _two_pick_home() -> dict:
    """The mocked Home query response the rendered-hero tests share."""
    return {
        'featuredProducts': [
            _hero_product('The Last Archive', 'the-last-archive'),
            _hero_product('A Room With Margins', 'a-room-with-margins'),
        ],
        'collections': [],
        'categories': [],
    }


class HomeHeroTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('plugins.installed.storefront.views.home.render')
    @patch('plugins.installed.storefront.views.home.internal_graphql', return_value={})
    def test_home_query_requests_slider_copy_fields(self, mocked_graphql, mocked_render):
        mocked_render.return_value = HttpResponse('ok')

        response = home(self.factory.get('/'))

        self.assertEqual(response.status_code, 200)
        query = mocked_graphql.call_args.args[0]
        self.assertIn('shortDescription', query)
        self.assertIn('category { name slug }', query)
        context = mocked_render.call_args.args[2]
        self.assertEqual(context['hero_products'], [])

    @patch(
        'plugins.installed.personalisation.services.rank_for_visitor',
        side_effect=lambda request, products, surface: products,
    )
    @patch('plugins.installed.storefront.views.home.internal_graphql')
    def test_homepage_renders_multi_slide_hero(self, mocked_graphql, _rank_for_visitor):
        mocked_graphql.return_value = _two_pick_home()

        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-home-hero')
        # One dot per book: a count below the number of hero products means a
        # book is unreachable. Counted on the dot→panel link, which appears once
        # per button and nowhere else — `data-home-hero-pick` also occurs in the
        # script's own selector, so counting the bare attribute is off by one.
        self.assertContains(response, 'aria-controls="hero-panel-', count=2)
        self.assertContains(response, 'The Last Archive')
        self.assertContains(response, 'A Room With Margins')
        # The restored editorial opening (the shop's first hero) leads the copy
        # column; the book title beneath it is the display-xl line of the
        # remembered "two big texts" composition.
        self.assertContains(response, 'The book that<br>moved this month')
        self.assertContains(response, 'window__book')
        self.assertNotContains(response, 'window__title')
        # Navigation is dot bullets (one per book), not the small-cover rail.
        self.assertContains(response, 'window__dot')
        self.assertNotContains(response, 'window__pick')

    @patch(
        'plugins.installed.personalisation.services.rank_for_visitor',
        side_effect=lambda request, products, surface: products,
    )
    @patch('plugins.installed.storefront.views.home.internal_graphql')
    def test_hero_drops_the_marketing_headline_and_decode_gimmick(
        self, mocked_graphql, _rank_for_visitor
    ):
        """The hero is the book, not an effect.

        Two display headlines competed in one column, and the per-letter decode
        scramble forced a JS font fitter plus a reserved tallest-title box to
        absorb the jitter it caused. Both are gone; this fails if either returns.
        """
        mocked_graphql.return_value = _two_pick_home()

        body = self.client.get('/').content.decode()

        self.assertNotIn('data-decode', body)
        self.assertNotIn('A moving shelf of the books', body)
        self.assertNotIn('fitHeroTitle', body)
        # The page had no h1 at all once the marketing h2 came out.
        self.assertEqual(body.count('<h1'), 1)
