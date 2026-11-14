"""An article's structured data and title say what a reader sees (v0.163.0).

Google's article page asks for an `image` that belongs to the article and reads
`articleBody` as text
(https://developers.google.com/search/docs/appearance/structured-data/article):
model-written posts carried markdown (`**`, `![…](…)`), so the body showed the
markers and the picture inside it was never the article's image. Titles: a
long journal post ended "… Examples —", and a stored genre title "…|dot books"
carried the brand a second time.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import json
import re
from types import SimpleNamespace

from django.test import TestCase

from plugins.installed.seo.services.meta import format_document_title

_MARKDOWN = (
    '## Why water first\n\n'
    '**Water** runs out before food does. '
    '![A rain barrel](/media/journal/barrel.jpg)\n\n'
    '- Store [two litres](https://example.com/guide) a day.\n'
    '- Rotate it every *six* months.\n'
)


def _graph(response) -> list[dict]:
    head = response.content.decode().split('</head>', 1)[0]
    nodes: list[dict] = []
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', head, re.S):
        nodes.extend(json.loads(block).get('@graph', []))
    return nodes


class ArticleNodeTests(TestCase):
    def _article(self, slug, body):
        from plugins.installed.cms.models import Page

        Page.objects.create(
            slug=slug,
            title='Water first',
            state='published',
            body=body,
            metadata={'category': 'journal'},
        )
        response = self.client.get(f'/journal/{slug}/')
        self.assertEqual(response.status_code, 200)
        return next(n for n in _graph(response) if n.get('@type') == 'BlogPosting')

    def test_a_markdown_body_is_plain_text_with_its_picture(self):
        node = self._article('water-first', _MARKDOWN)
        body = node['articleBody']
        self.assertTrue(body.startswith('Why water first Water runs out before food does.'))
        for marker in ('**', '![', '](', '##', '<'):
            self.assertNotIn(marker, body)
        self.assertIn('Store two litres a day.', body)
        image = node['image'] if isinstance(node['image'], str) else node['image'][0]
        self.assertTrue(image.startswith('http'))
        self.assertTrue(image.endswith('/media/journal/barrel.jpg'))

    def test_a_long_body_is_cut_under_5000_at_a_sentence(self):
        node = self._article('water-long', '<p>' + 'Store water for every day. ' * 400 + '</p>')
        body = node['articleBody']
        self.assertLess(len(body), 5000)
        self.assertTrue(body.endswith('day.'))

    def test_no_picture_no_image(self):
        node = self._article('water-plain', '<p>Water runs out first.</p>')
        self.assertNotIn('image', node)


class DocumentTitleTests(TestCase):
    def _row(self, brand='Dot Books.'):
        return SimpleNamespace(organization_name=brand, title_template='', title_max_length=60)

    def test_a_long_post_drops_its_section_whole(self):
        title = format_document_title(
            'Borrowed Time: How Long Your Supplies Last, With Examples — Journal',
            settings_row=self._row(),
        )
        self.assertEqual(title, 'Borrowed Time: How Long Your Supplies Last, With Examples')

    def test_a_cut_never_ends_on_a_separator(self):
        title = format_document_title(
            'word ' * 11 + '— tail of the title', settings_row=self._row()
        )
        self.assertLessEqual(len(title), 60)
        self.assertFalse(title.endswith(('—', '-', '|', ' ')))

    def test_a_short_head_keeps_words_of_its_subtitle(self):
        title = format_document_title(
            'Dune - a desert planet, a spice, a family and a war across many worlds',
            settings_row=self._row(),
        )
        self.assertTrue(title.startswith('Dune - a desert planet'))
        self.assertLessEqual(len(title), 60)

    def test_a_stored_brand_suffix_is_not_doubled(self):
        for stored in (
            'Adventure Books - Swashbuckling, Survival & Magic|dot books',
            'Adventure Books - Swashbuckling, Survival & Magic | Dot Books.',
            'Adventure Books - Swashbuckling, Survival & Magic — DOT BOOKS',
        ):
            with self.subTest(stored=stored):
                self.assertEqual(
                    format_document_title(stored, settings_row=self._row()),
                    'Adventure Books - Swashbuckling, Survival & Magic',
                )

    def test_a_word_ending_like_the_brand_is_kept(self):
        self.assertEqual(
            format_document_title('Notebooks', settings_row=self._row('Books')),
            'Notebooks — Books',
        )


class ItemListUrlTests(TestCase):
    def test_every_list_entry_is_absolute(self):
        from plugins.installed.seo.schema.graph import _absolute_list_urls

        graph = {
            '@graph': [
                {
                    '@type': 'WebPage',
                    'mainEntity': {
                        '@type': 'ItemList',
                        'itemListElement': [
                            {'@type': 'ListItem', 'position': 1, 'url': '/products/a/'},
                            {'@type': 'ListItem', 'position': 2, 'item': '/products/b/'},
                            {
                                '@type': 'ListItem',
                                'position': 3,
                                'item': {'url': '/products/c/', 'image': '/media/c.jpg'},
                            },
                            {'@type': 'ListItem', 'position': 4, 'url': 'https://cdn.test/d/'},
                            {'@type': 'ListItem', 'position': 5, 'url': '//cdn.test/e/'},
                        ],
                    },
                }
            ]
        }
        _absolute_list_urls(graph, 'https://shop.test')
        items = graph['@graph'][0]['mainEntity']['itemListElement']
        self.assertEqual(items[0]['url'], 'https://shop.test/products/a/')
        self.assertEqual(items[1]['item'], 'https://shop.test/products/b/')
        self.assertEqual(items[2]['item']['url'], 'https://shop.test/products/c/')
        self.assertEqual(items[2]['item']['image'], 'https://shop.test/media/c.jpg')
        self.assertEqual(items[3]['url'], 'https://cdn.test/d/')
        self.assertEqual(items[4]['url'], '//cdn.test/e/')

    def test_a_rendered_listing_names_absolute_urls(self):
        from decimal import Decimal

        from djmoney.money import Money

        from plugins.installed.catalog.models import Category, Product

        category = Category.objects.create(name='Water', slug='water-list', is_active=True)
        for n in (1, 2):
            Product.objects.create(
                name=f'Filter {n}',
                slug=f'filter-list-{n}',
                sku=f'FL-{n}',
                status='active',
                price=Money(Decimal('10.00'), 'USD'),
                category=category,
            )
        response = self.client.get('/products/')
        self.assertEqual(response.status_code, 200)
        lists = [
            n['mainEntity']
            for n in _graph(response)
            if isinstance(n.get('mainEntity'), dict) and n['mainEntity'].get('@type') == 'ItemList'
        ]
        self.assertTrue(lists)
        for entry in lists[0]['itemListElement']:
            for value in (entry.get('url'), entry.get('item')):
                target = value.get('url') if isinstance(value, dict) else value
                if target:
                    self.assertTrue(target.startswith('http'), target)
