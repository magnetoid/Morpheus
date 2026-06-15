"""classify_books management command — LLM mocked, assert genre/topic tagging."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct, Genre, Topic
from plugins.installed.catalog.models import Product

_FAKE_JSON = '[{"i":1,"genres":["Classics","Adventure"],"topics":["Whaling","Obsession"]}]'


class _FakeLLM:
    def complete(self, prompt, **kw):
        return _FAKE_JSON


def _book(slug, sku, **kw):
    p = Product.objects.create(
        name=slug, slug=slug, sku=sku, price=Money(Decimal('9'), 'USD'), status='active'
    )
    return BookProduct.objects.create(product=p, **kw)


class ClassifyBooksTests(TestCase):
    @patch('plugins.installed.ai_assistant.services.llm.get_llm', return_value=_FakeLLM())
    def test_apply_tags_genres_and_topics(self, _):
        book = _book('moby-dick', 'SKUM', synopsis='A whale, an obsession.')
        call_command('classify_books', '--apply', '--limit', '1', stdout=StringIO())
        book.refresh_from_db()
        self.assertEqual(set(book.genres.values_list('name', flat=True)), {'Classics', 'Adventure'})
        self.assertEqual(set(book.topics.values_list('name', flat=True)), {'Whaling', 'Obsession'})
        # Terms are deduped by slug (idempotent).
        self.assertEqual(Genre.objects.filter(slug='classics').count(), 1)
        self.assertEqual(Topic.objects.filter(slug='whaling').count(), 1)

    @patch('plugins.installed.ai_assistant.services.llm.get_llm', return_value=_FakeLLM())
    def test_dry_run_writes_nothing(self, _):
        book = _book('moby-2', 'SKUM2')
        call_command('classify_books', '--limit', '1', stdout=StringIO())
        book.refresh_from_db()
        self.assertEqual(book.genres.count(), 0)
        self.assertEqual(book.topics.count(), 0)

    @patch('plugins.installed.ai_assistant.services.llm.get_llm', return_value=_FakeLLM())
    def test_replace_clears_existing(self, _):
        book = _book('moby-3', 'SKUM3')
        old = Genre.objects.create(name='Editors Pick', slug='editors-pick')
        book.genres.add(old)
        call_command('classify_books', '--apply', '--replace', '--limit', '1', stdout=StringIO())
        book.refresh_from_db()
        self.assertNotIn('editors-pick', book.genres.values_list('slug', flat=True))
        self.assertIn('classics', book.genres.values_list('slug', flat=True))
