"""Language editions — translation_of linking, the editions helper, and the
PDP switcher/hreflang template tags."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.book_product.dashboard import save_book_fields
from plugins.installed.book_product.models import BookProduct
from plugins.installed.book_product.templatetags.book_extras import (
    book_language_editions,
    language_name,
)
from plugins.installed.catalog.models import Product


def _book(slug: str, language: str, status: str = 'active'):
    product = Product.objects.create(
        name=f'Work ({language})',
        slug=slug,
        sku=f'SKU-{slug}',
        status=status,
        price=Money(Decimal('9.00'), 'USD'),
    )
    return BookProduct.objects.create(product=product, language=language)


class TranslationLinkTests(TestCase):
    def test_save_links_translation_by_slug(self):
        original = _book('work-en', 'en')
        fr = _book('work-fr', 'fr')
        save_book_fields(fr.product, {'translation_of': 'work-en'})
        fr.refresh_from_db()
        self.assertEqual(fr.translation_of_id, original.pk)

    def test_linking_to_a_translation_resolves_to_the_original(self):
        original = _book('work-en', 'en')
        fr = _book('work-fr', 'fr')
        fr.translation_of = original
        fr.save()
        de = _book('work-de', 'de')
        save_book_fields(de.product, {'translation_of': 'work-fr'})
        de.refresh_from_db()
        self.assertEqual(de.translation_of_id, original.pk)

    def test_blank_unlinks_and_unknown_is_noop(self):
        original = _book('work-en', 'en')
        fr = _book('work-fr', 'fr')
        fr.translation_of = original
        fr.save()
        save_book_fields(fr.product, {'translation_of': 'no-such-slug'})
        fr.refresh_from_db()
        self.assertEqual(fr.translation_of_id, original.pk)  # unknown → unchanged
        save_book_fields(fr.product, {'translation_of': ''})
        fr.refresh_from_db()
        self.assertIsNone(fr.translation_of_id)  # blank → unlinked


class LanguageEditionsTests(TestCase):
    def test_editions_original_first_active_only(self):
        original = _book('work-en', 'en')
        fr = _book('work-fr', 'fr')
        de = _book('work-de', 'de', status='draft')  # inactive — excluded
        fr.translation_of = original
        de.translation_of = original
        fr.save()
        de.save()
        for b in (original, fr):
            editions = b.language_editions()
            self.assertEqual([e.pk for e in editions], [original.pk, fr.pk])

    def test_switcher_tag_shapes_and_self_gates(self):
        original = _book('work-en', 'en')
        self.assertEqual(book_language_editions({'slug': 'work-en'}), [])  # single edition
        fr = _book('work-fr', 'fr')
        fr.translation_of = original
        fr.save()
        rows = book_language_editions({'slug': 'work-fr'})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['slug'], 'work-en')
        self.assertFalse(rows[0]['current'])
        self.assertTrue(rows[1]['current'])

    def test_language_name_filter(self):
        self.assertEqual(language_name('fr'), 'français')
        self.assertEqual(language_name(''), '')
        self.assertEqual(language_name('zz-unknown'), 'zz-unknown')
