"""Book filters for the all-books page: what each facet narrows and counts.

Values inside one facet widen (OR); facets narrow each other (AND). A facet's
counts are taken with every OTHER facet applied, so a number next to a choice
says how many books that choice would leave.
"""

from __future__ import annotations

from decimal import Decimal

from django.http import QueryDict
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.listing_facets import (
    SORTS,
    answer,
    apply,
    describe,
    selections,
)
from plugins.installed.book_product.models import BookProduct, Genre, Topic
from plugins.installed.catalog.models import Product, ProductVariant


def _book(slug, *, author='', pages=None, genres=(), topics=(), variants=()):
    p = Product.objects.create(
        name=slug.replace('-', ' ').title(),
        slug=slug,
        sku=slug.upper(),
        price=Money(Decimal('9.00'), 'USD'),
        product_type='variable' if variants else 'simple',
        status='active',
    )
    b = BookProduct.objects.create(product=p, author=author, page_count=pages)
    b.genres.set(genres)
    b.topics.set(topics)
    for i, (name, vtype) in enumerate(variants):
        ProductVariant.objects.create(
            product=p,
            name=name,
            sku=f'{slug}-{i}',
            price=Money(Decimal('9.00'), 'USD'),
            variant_type=vtype,
        )
    return p


def _q(query: str) -> QueryDict:
    return QueryDict(query)


def _facet(facets, key):
    return next(f for f in facets if f['key'] == key)


def _counts(facet):
    return {o['value']: o['count'] for o in facet['options']}


class FacetFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fantasy = Genre.objects.create(name='Fantasy', slug='fantasy')
        cls.mystery = Genre.objects.create(name='Mystery', slug='mystery')
        cls.love = Topic.objects.create(name='Love', slug='love')
        cls.spies = Topic.objects.create(name='Espionage', slug='espionage')
        cls.once = Topic.objects.create(name='Lighthouses', slug='lighthouses')
        cls.a = _book(
            'dragon',
            author='Ursula Le Guin',
            pages=120,
            genres=[cls.fantasy],
            topics=[cls.love],
            variants=[('Print', 'physical'), ('Digital PDF', 'digital')],
        )
        cls.b = _book(
            'quest',
            author='Ursula Le Guin',
            pages=420,
            genres=[cls.fantasy],
            topics=[cls.love, cls.spies],
            variants=[('Digital PDF', 'digital'), ('Audiobook', 'digital')],
        )
        cls.c = _book(
            'murder',
            author='Agatha Christie',
            pages=250,
            genres=[cls.mystery],
            topics=[cls.spies, cls.once],
        )
        cls.d = _book('notes', author='', pages=None, genres=[cls.mystery], topics=[cls.love])

    def base(self):
        return Product.objects.filter(status='active')


class SelectionTests(TestCase):
    def test_repeated_keys_become_lists_without_blanks_or_repeats(self):
        chosen = selections(_q('genre=a&genre=b&genre=a&genre=&topic=x&sort=name'))
        self.assertEqual(chosen['genre'], ['a', 'b'])
        self.assertEqual(chosen['topic'], ['x'])
        self.assertEqual(chosen['author'], [])
        self.assertEqual(set(chosen), {'genre', 'topic', 'author', 'format', 'length'})


class ApplyTests(FacetFixture):
    def _slugs(self, query):
        return set(apply(self.base(), selections(_q(query))).values_list('slug', flat=True))

    def test_values_inside_a_facet_widen(self):
        self.assertEqual(
            self._slugs('genre=fantasy&genre=mystery'), {'dragon', 'quest', 'murder', 'notes'}
        )

    def test_facets_narrow_each_other(self):
        self.assertEqual(self._slugs('genre=fantasy&topic=espionage'), {'quest'})

    def test_author_matches_ignoring_case(self):
        self.assertEqual(self._slugs('author=agatha%20christie'), {'murder'})

    def test_length_buckets_and_books_without_a_page_count(self):
        self.assertEqual(self._slugs('length=under-150'), {'dragon'})
        self.assertEqual(self._slugs('length=150-300&length=300-500'), {'murder', 'quest'})
        self.assertNotIn(
            'notes', self._slugs('length=under-150&length=150-300&length=300-500&length=500-plus')
        )

    def test_format_rules(self):
        self.assertEqual(self._slugs('format=print'), {'dragon', 'murder', 'notes'})
        self.assertEqual(self._slugs('format=digital'), {'dragon', 'quest'})
        self.assertEqual(self._slugs('format=audiobook'), {'quest'})

    def test_an_unknown_value_narrows_to_nothing_not_everything(self):
        self.assertEqual(self._slugs('genre=no-such-genre'), set())

    def test_an_unknown_format_or_length_is_ignored(self):
        self.assertEqual(len(self._slugs('format=vinyl')), 4)
        self.assertEqual(len(self._slugs('length=huge')), 4)


class DescribeTests(FacetFixture):
    def test_counts_ignore_the_facets_own_choice(self):
        facets = describe(self.base(), selections(_q('genre=fantasy')))
        self.assertEqual(_counts(_facet(facets, 'genre')), {'fantasy': 2, 'mystery': 2})
        # Another facet's counts are narrowed by the chosen genre.
        self.assertEqual(_counts(_facet(facets, 'author')), {'Ursula Le Guin': 2})

    def test_a_choice_that_leaves_nothing_is_hidden_unless_selected(self):
        facets = describe(self.base(), selections(_q('genre=mystery&format=audiobook')))
        # Genre counts ignore the chosen genre: the one audiobook is a fantasy book.
        # Mystery leaves nothing with audiobook, but it is selected, so it stays at 0.
        self.assertEqual(_counts(_facet(facets, 'genre')), {'fantasy': 1, 'mystery': 0})
        # Format counts ignore the chosen format: the two mystery books are print only.
        # Digital leaves nothing and isn't selected, so it is hidden.
        self.assertEqual(_counts(_facet(facets, 'format')), {'print': 2, 'audiobook': 0})

    def test_a_topic_with_one_book_is_not_listed(self):
        topics = _counts(_facet(describe(self.base(), selections(_q(''))), 'topic'))
        self.assertEqual(topics, {'love': 3, 'espionage': 2})

    def test_a_selected_author_typed_in_another_case_is_shown_selected(self):
        author = _facet(describe(self.base(), selections(_q('author=agatha%20christie'))), 'author')
        chosen = [o for o in author['options'] if o['selected']]
        self.assertEqual([o['value'] for o in chosen], ['Agatha Christie'])

    def test_order_labels_and_search(self):
        facets = describe(self.base(), selections(_q('')))
        self.assertEqual(
            [f['key'] for f in facets], ['genre', 'topic', 'author', 'format', 'length']
        )
        self.assertTrue(_facet(facets, 'topic')['searchable'])
        self.assertTrue(_facet(facets, 'author')['searchable'])
        self.assertFalse(_facet(facets, 'genre')['searchable'])
        self.assertEqual(
            [o['label'] for o in _facet(facets, 'format')['options']],
            ['Print', 'Digital PDF', 'Audiobook'],
        )
        self.assertEqual(
            _counts(_facet(facets, 'length')), {'under-150': 1, '150-300': 1, '300-500': 1}
        )


class AnswerTests(FacetFixture):
    def test_the_hook_answer_narrows_and_describes(self):
        out = answer(
            {'queryset': self.base(), 'facets': [], 'sorts': [], 'chosen': {}}, _q('genre=mystery')
        )
        self.assertEqual(set(out['queryset'].values_list('slug', flat=True)), {'murder', 'notes'})
        self.assertEqual(out['chosen'], {'genre': ['mystery']})
        self.assertEqual([s[0] for s in out['sorts']], [s[0] for s in SORTS])
        # Topic is left out: no topic covers two of the mystery books (an empty facet is dropped).
        self.assertEqual([f['key'] for f in out['facets']], ['genre', 'author', 'format', 'length'])

    def test_sorts_by_author_and_length(self):
        by_author = dict((k, o) for k, _l, o in SORTS)
        names = list(self.base().order_by(*by_author['author']).values_list('slug', flat=True))
        # Books without an author come last, not first.
        self.assertEqual(names, ['murder', 'dragon', 'quest', 'notes'])
        shortest = list(self.base().order_by(*by_author['shortest']).values_list('slug', flat=True))
        self.assertEqual(shortest, ['dragon', 'murder', 'quest', 'notes'])


class LazyPanelTests(FacetFixture):
    """Topic and Author list every choice only when their panel opens (v0.125.0).

    The all-books page sent dotbooks' 340 topics and 291 authors as checkboxes on
    every view, about a third of its HTML. The page now carries the chosen ones (for
    the chips, the heading and Apply) and the panel fetches the rest.
    """

    def _answer(self, query):
        value = {'queryset': self.base(), 'facets': [], 'sorts': [], 'chosen': {}}
        return answer(value, _q(query))

    def test_topic_and_author_carry_only_what_is_chosen(self):
        facets = self._answer('')['facets']
        for key, url in (('topic', '/topics/'), ('author', '/authors/')):
            facet = _facet(facets, key)
            self.assertTrue(facet['lazy'])
            self.assertEqual(facet['options'], [])
            self.assertEqual(facet['more_url'], url)
        self.assertFalse(_facet(facets, 'genre').get('lazy'))
        self.assertEqual(_counts(_facet(facets, 'genre')), {'fantasy': 2, 'mystery': 2})

    def test_a_chosen_topic_and_author_keep_their_labels(self):
        facets = self._answer('topic=espionage&author=agatha%20christie')['facets']
        topic = _facet(facets, 'topic')
        self.assertEqual(
            [(o['value'], o['label'], o['selected']) for o in topic['options']],
            [('espionage', 'Espionage', True)],
        )
        author = _facet(facets, 'author')
        self.assertEqual([o['value'] for o in author['options']], ['Agatha Christie'])
        self.assertEqual(author['selected_count'], 1)

    def test_a_panel_nothing_would_fill_is_left_out(self):
        # No topic covers two mystery books (DescribeTests), so there is no Topic panel.
        keys = [f['key'] for f in self._answer('genre=mystery')['facets']]
        self.assertNotIn('topic', keys)
        self.assertIn('author', keys)

    def test_an_opened_panel_gets_its_whole_list(self):
        out = self._answer('facet_panel=topic&genre=fantasy')
        self.assertEqual([f['key'] for f in out['facets']], ['topic'])
        topic = out['facets'][0]
        self.assertFalse(topic.get('lazy'))
        self.assertEqual(_counts(topic), {'love': 2})  # espionage covers one fantasy book
        self.assertEqual(set(out['queryset'].values_list('slug', flat=True)), {'dragon', 'quest'})

    def test_an_author_typed_in_another_case_is_the_stored_name_in_the_panel_too(self):
        # Agatha Christie wrote no fantasy book, so she is not in the opened list's rows;
        # her box must carry the same value the page gave it, or closing the panel
        # would read as a change and reload the page.
        page = _facet(self._answer('author=agatha%20christie&genre=fantasy')['facets'], 'author')
        panel = self._answer('facet_panel=author&author=agatha%20christie&genre=fantasy')
        chosen = [o['value'] for o in panel['facets'][0]['options'] if o['selected']]
        self.assertEqual(chosen, [o['value'] for o in page['options']])
        self.assertEqual(chosen, ['Agatha Christie'])

    def test_chosen_authors_cost_one_query_however_many(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def queries(query):
            with CaptureQueriesContext(connection) as ctx:
                self._answer(query)
            return len(ctx.captured_queries)

        one = queries('author=a1')
        self.assertEqual(queries('author=a1&author=a2&author=a3&author=a4&author=a5'), one)
