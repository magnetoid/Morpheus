"""Tests for the book_extras template filters/tags used by storefront cards."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.book_product.templatetags.book_extras import (
    book_term_lede,
    first_sentence,
)


class FirstSentenceTests(TestCase):
    def test_plain_text_first_sentence(self):
        self.assertEqual(first_sentence('One. Two.'), 'One.')

    def test_strips_markup_and_entities(self):
        # Regression: some stored copy contains a literal <p> and pre-escaped
        # entities — cards showed "&lt;p&gt;…&#x27;…" verbatim on the storefront.
        raw = '<p>Walt Whitman&#x27;s &#x27;Leaves of Grass&#x27; is wild. More.</p>'
        self.assertEqual(first_sentence(raw), "Walt Whitman's 'Leaves of Grass' is wild.")

    def test_survives_double_escaped_input(self):
        # firstof-as style plumbing escapes once more: &amp;#x27; / &amp;lt;
        raw = '&amp;lt;p&amp;gt;A feverish descent&amp;#x27;s tale. Rest.'
        self.assertEqual(first_sentence(raw), "A feverish descent's tale.")

    def test_empty_and_none(self):
        self.assertEqual(first_sentence(''), '')
        self.assertEqual(first_sentence(None), '')


class BookTermLedeTests(TestCase):
    def test_returns_description_for_matching_term(self):
        from plugins.installed.book_product.models import BookTaxonomyTerm

        BookTaxonomyTerm.objects.create(
            taxonomy='author',
            slug='jane-austen',
            name='Jane Austen',
            description='Sharp comedies of manners.',
        )
        self.assertEqual(book_term_lede('author', 'Jane Austen'), 'Sharp comedies of manners.')

    def test_blank_for_unknown_or_empty(self):
        self.assertEqual(book_term_lede('author', 'Nobody Realname'), '')
        self.assertEqual(book_term_lede('author', ''), '')
