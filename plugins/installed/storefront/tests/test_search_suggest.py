"""What the search dropdown suggests (/api/quick-search/, `storefront/search_suggest.py`).

A suggestion is what was typed. The dropdown used the semantic ranker of the full
results page, which finds a neighbour for any query: live, "dune" and "orwell"
suggested the same six unrelated books, and "wat" on the survival store missed
every water filter. It now matches words as typed and puts the landing pages
whose names match (categories, collections, an app's own) above the products.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Category, Collection, Product


def _product(name, slug, **kw):
    kw = {'status': 'active', 'product_type': 'simple', **kw}
    return Product.objects.create(
        name=name, slug=slug, sku=slug.upper(), price=Money(Decimal('10.00'), 'USD'), **kw
    )


class SuggestTests(TestCase):
    def _get(self, q):
        response = self.client.get('/api/quick-search/', {'q': q})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _slugs(self, q):
        return [r['slug'] for r in self._get(q)['results']]

    def test_every_word_must_start_a_word_of_the_name(self):
        _product('Water Filter Bottle', 'water-filter-bottle')
        _product('Ferro Rod Fire Starter', 'ferro-rod')
        _product('Stopwatch', 'stopwatch')  # "wat" inside a word is not what was typed
        self.assertEqual(self._slugs('wat'), ['water-filter-bottle'])
        self.assertEqual(self._slugs('filt wat'), ['water-filter-bottle'])
        self.assertEqual(self._slugs('water rod'), [])

    def test_a_name_that_starts_with_the_query_comes_first(self):
        _product('Emergency Water Pouches', 'pouches')
        _product('Water Storage Tank', 'tank')
        self.assertEqual(self._slugs('water'), ['tank', 'pouches'])

    def test_text_fills_in_after_names_for_longer_words(self):
        _product('Turkey Tail Capsules', 'turkey-tail', description='<p>A medicinal mushroom.</p>')
        _product('Mushroom Coffee', 'mushroom-coffee')
        self.assertEqual(self._slugs('mush'), ['mushroom-coffee', 'turkey-tail'])

    def test_short_words_never_match_a_products_html(self):
        _product('Plain Item', 'plain-item', description='<p><span>Nothing here.</span></p>')
        self.assertEqual(self._slugs('sp'), [])

    def test_the_semantic_ranker_is_left_to_the_results_page(self):
        unrelated = _product('The Huguenots in France', 'huguenots')

        def _neighbours(value, **kwargs):
            return [unrelated.pk]

        hook_registry.register(MorpheusEvents.SEARCH_RANKED_IDS, _neighbours, priority=10)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.SEARCH_RANKED_IDS, _neighbours)
        self.assertEqual(self._slugs('dune'), [])

    def test_drafts_and_services_are_never_suggested(self):
        _product('Kayak Draft', 'kayak-draft', status='draft')
        _product('Kayak Tour', 'kayak-tour', product_type='service')
        self.assertEqual(self._slugs('kayak'), [])

    def test_categories_with_products_are_suggested_with_their_count(self):
        water = Category.objects.create(name='Water Filters & Purification', slug='water-filters')
        child = Category.objects.create(name='Gravity Filters', slug='gravity', parent=water)
        Category.objects.create(name='Water Storage', slug='water-storage')  # nothing in it
        _product('Gravity Bag', 'gravity-bag', category=child)
        groups = self._get('water')['groups']
        self.assertEqual(
            groups,
            [
                {
                    'key': 'categories',
                    'label': 'Categories',
                    'items': [
                        {
                            'name': 'Water Filters & Purification',
                            'url': '/category/water-filters/',
                            'meta': '1 product',
                        }
                    ],
                }
            ],
        )

    def test_collections_with_products_are_suggested(self):
        gifts = Collection.objects.create(name='Gift Ideas', slug='gift-ideas')
        _product('Candle Set', 'candle-set').collections.add(gifts)
        Collection.objects.create(name='Gifts Archive', slug='gifts-archive', is_active=False)
        [group] = self._get('gift')['groups']
        self.assertEqual(group['key'], 'collections')
        self.assertEqual([i['url'] for i in group['items']], ['/collection/gift-ideas/'])

    def test_an_app_adds_its_own_landing_pages(self):
        def _authors(value, query='', words=(), **kwargs):
            return [*value, {'key': 'authors', 'label': 'Authors', 'items': [{'name': query}]}]

        hook_registry.register(MorpheusEvents.SEARCH_SUGGESTIONS, _authors, priority=10)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.SEARCH_SUGGESTIONS, _authors)
        groups = self._get('Orwell')['groups']
        self.assertEqual(groups[-1]['items'], [{'name': 'Orwell'}])
