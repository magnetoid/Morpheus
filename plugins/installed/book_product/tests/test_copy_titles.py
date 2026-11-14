"""A generated genre title never carries the shop's name (v0.163.0).

dotbooks' genre pages read "Adventure Books - Swashbuckling, Survival &
Magic|dot books": the copy prompt asked for an SEO title on "dot books" and the
model put the name on its end, while the head adds the brand to every title.
The prompt now says so, and a name the model adds anyway is taken off.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from django.test import TestCase

from core.models import StoreSettings
from plugins.installed.book_product.models import BookProduct, Genre
from plugins.installed.book_product.services_copy import (
    _without_shop_name,
    build_prompt,
    generate_copy,
)
from plugins.installed.catalog.models import Product


class WithoutShopNameTests(TestCase):
    def test_the_name_after_any_separator_goes(self):
        for stored in (
            'Adventure Books - Swashbuckling, Survival & Magic|dot books',
            'Adventure Books - Swashbuckling, Survival & Magic | Dot Books.',
            'Adventure Books - Swashbuckling, Survival & Magic — DOT BOOKS',
        ):
            with self.subTest(stored=stored):
                self.assertEqual(
                    _without_shop_name(stored, 'Dot Books.'),
                    'Adventure Books - Swashbuckling, Survival & Magic',
                )

    def test_a_title_that_only_mentions_books_is_kept(self):
        self.assertEqual(_without_shop_name('Poetry Books', 'Books'), 'Poetry Books')
        self.assertEqual(_without_shop_name('Poetry - Books', ''), 'Poetry - Books')


class GeneratedTitleTests(TestCase):
    def setUp(self):
        StoreSettings.objects.create(store_name='dot books')
        product = Product.objects.create(
            name='A Voyage', slug='a-voyage', sku='VOY-1', price=5, status='active'
        )
        book = BookProduct.objects.create(product=product)
        book.genres.add(Genre.objects.create(name='Adventure', slug='adventure'))

    def test_the_prompt_asks_for_a_title_without_the_name(self):
        prompt = build_prompt('the Adventure genre', 'Books: A Voyage')
        self.assertIn('called dot books', prompt)
        self.assertIn("without the shop's name", prompt)

    def test_a_name_the_model_adds_anyway_is_taken_off(self):
        raw = json.dumps(
            {
                'description': 'Swashbuckling stories of survival and magic, chosen with care.',
                'meta_title': 'Adventure Books - Swashbuckling, Survival & Magic|dot books',
                'meta_description': 'Adventure stories.',
            }
        )
        gateway = type('G', (), {'complete': lambda self, *a, **k: raw})()
        with patch('plugins.installed.ai_assistant.services.llm.get_llm', return_value=gateway):
            out = generate_copy('genre', 'adventure')
        self.assertEqual(out['meta_title'], 'Adventure Books - Swashbuckling, Survival & Magic')
