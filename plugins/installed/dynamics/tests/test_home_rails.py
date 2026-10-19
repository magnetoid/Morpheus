"""Home-page carousels: a shelf, New in and Best sellers, drawn as the theme's rails.

Supernatural's owner asked for fewer products per row and more carousels
(2026-10-19): one per shelf, New in and Best sellers. A dynamics block does each,
so the merchant changes them where the other blocks live. Four things had to hold
first. A "Carousel" block drew a grid of its own plainer cards, beside rails with
arrows and Add to cart. A shelf named its category but not its subcategories
(CLAUDE.md: a category lists its subtree). A shelf showed products without a photo
as readily as products with one. And Best sellers showed the newest products when
nothing had sold, under a heading that says they sell.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.catalog.models import Category, Product, ProductImage
from plugins.installed.dynamics.models import DynamicBlock
from plugins.installed.dynamics.services import recommend, see_all_url


def _product(slug, *, category=None, photo=False, days_old=0):
    product = Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('10.00'), 'USD'),
        status='active',
        category=category,
    )
    if days_old:
        Product.objects.filter(pk=product.pk).update(
            created_at=timezone.now() - timedelta(days=days_old)
        )
    if photo:
        ProductImage.objects.create(product=product, image=f'products/{slug}.png', is_primary=True)
    return product


def _block(strategy='manual', categories=(), **fields):
    block = DynamicBlock.objects.create(
        name='B', slot='home_after_rails', strategy=strategy, limit=8, **fields
    )
    if categories:
        block.categories.set(categories)
    return block


def _ids(block):
    return [p.pk for p in recommend(block, request=RequestFactory().get('/'))]


class ShelfTests(TestCase):
    def setUp(self):
        self.shelf = Category.objects.create(name='Pantry', slug='pantry')
        self.sub = Category.objects.create(name='Oils', slug='oils', parent=self.shelf)

    def test_a_shelf_lists_the_products_of_its_subcategories(self):
        oil = _product('olive-oil', category=self.sub)
        self.assertIn(oil.pk, _ids(_block(categories=[self.shelf])))

    def test_a_shelf_lists_products_with_a_photo_first(self):
        bare = _product('bare', category=self.shelf)
        shown = _product('shown', category=self.shelf, photo=True, days_old=30)
        self.assertEqual(_ids(_block(categories=[self.shelf]))[:2], [shown.pk, bare.pk])


class BestSellerTests(TestCase):
    def test_best_sellers_show_nothing_before_the_first_sale(self):
        _product('new-tea')
        self.assertEqual(_ids(_block(strategy='best_sellers')), [])


class SeeAllTests(TestCase):
    def test_a_one_shelf_block_links_to_the_shelf(self):
        shelf = Category.objects.create(name='Teas', slug='teas')
        self.assertEqual(see_all_url(_block(categories=[shelf])), '/category/teas/')

    def test_new_in_links_to_the_newest_products(self):
        self.assertEqual(see_all_url(_block(strategy='new_arrivals')), '/products/?sort=newest')

    def test_a_block_no_listing_can_show_has_no_link(self):
        shelf = Category.objects.create(name='Teas', slug='teas')
        self.assertEqual(see_all_url(_block(categories=[shelf], tags=['sale'])), '')
        self.assertEqual(see_all_url(_block(strategy='best_sellers')), '')


class CarouselRenderTests(TestCase):
    def setUp(self):
        self.product = _product('rail-probe', photo=True)

    def _render(self, **context):
        return render_to_string(
            'dynamics/_carousel.html',
            {'products': [self.product], 'heading': 'New in', **context},
        )

    def test_a_carousel_is_the_themes_rail_of_its_own_product_cards(self):
        html = self._render(layout='carousel', show_title=True, show_price=True)
        self.assertIn('data-book-rail', html)
        self.assertIn('data-rail-next', html)
        self.assertIn('data-product-card', html)
        self.assertIn(f'/cart/add/{self.product.pk}/', html)

    def test_a_carousel_that_hides_titles_keeps_its_own_cards_in_the_rail(self):
        html = self._render(layout='carousel', show_title=False, show_price=True)
        self.assertIn('data-book-rail', html)
        self.assertNotIn('data-product-card', html)

    def test_a_grid_is_unchanged(self):
        html = self._render(layout='grid', columns=4, show_title=True, show_price=True)
        self.assertNotIn('data-book-rail', html)
        self.assertNotIn('data-product-card', html)
        self.assertIn('repeat(4, minmax(0,1fr))', html)

    def test_a_shelf_carousel_links_to_its_shelf(self):
        html = self._render(layout='carousel', see_all='/category/pantry/')
        self.assertIn('href="/category/pantry/"', html)
