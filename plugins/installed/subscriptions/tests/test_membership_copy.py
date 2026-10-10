"""The membership page speaks for the store, not for the first bookshop."""

from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase


class MembershipCopyTests(SimpleTestCase):
    def test_no_bookshop_words(self):
        template = Path(__file__).resolve().parents[1] / 'templates/subscriptions/membership.html'
        source = template.read_text(encoding='utf-8').lower()
        for word in ('bookstore', 'bookshop', 'books'):
            with self.subTest(word=word):
                self.assertNotIn(word, source)
