"""The seeded legal pages belong to any store, not to the first one.

The accessibility and cookie policies seeded on every store said "browse and
buy books" and "which pages and titles readers use" — bookshop copy on a
survival-supplies store.
"""

from __future__ import annotations

from django.test import SimpleTestCase


class SeedCopyIsVerticalNeutralTests(SimpleTestCase):
    def test_no_bookshop_words_in_the_seed(self):
        import inspect

        from plugins.installed.gdpr import services

        source = inspect.getsource(services).lower()
        for word in ('bookstore', 'bookshop', 'buy books', 'titles readers'):
            with self.subTest(word=word):
                self.assertNotIn(word, source)
