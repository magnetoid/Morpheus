"""The shell must never publish one store's brand on another store.

`dot books` was hardcoded inside SEO descriptions across the storefront shell,
so two other live businesses introduced themselves to Google as a bookshop:

    supernatural-shop.com /about/     "dot books is an independent bookshop…"
    montenegro-experience.me /shipping/  "How dot books ships your order —
                                          tracked, signed-for, free over $40."

The shipping line is the serious one. It is a commercial claim, published on
stores whose checkout says nothing of the kind — the same shape as the invented
`shippingDetails` in the offer-claims landmine: a promise checkout will break.
"""

from __future__ import annotations

import pathlib
import re

from django.test import TestCase

from plugins.installed.storefront.services import catalogue_label, store_blurb, store_name

# Files that may legitimately mention the name (its own theme, its own tests).
_SHELL = ('plugins/installed/storefront/views', 'templates')
_BRAND = re.compile(r'dot\s*books', re.I)
_BOOK_LABEL = re.compile(r"['\"]All books['\"]")


class NoForeignBrandTests(TestCase):
    def test_the_shell_hardcodes_no_store_brand(self):
        repo = pathlib.Path(__file__).resolve().parents[4]
        offenders = []
        for rel in _SHELL:
            for path in (repo / rel).rglob('*'):
                if path.suffix not in {'.py', '.html'}:
                    continue
                for i, line in enumerate(path.read_text(errors='ignore').splitlines(), 1):
                    # A comment explaining the bug is not the bug.
                    stripped = line.strip()
                    if stripped.startswith(('#', '{#')) or 'used to' in line or 'hardcoded' in line:
                        continue
                    if _BRAND.search(line):
                        offenders.append(f'{path.relative_to(repo)}:{i}')
        self.assertEqual(
            offenders,
            [],
            f'a store brand is hardcoded in the shared shell: {offenders}',
        )

    def test_the_shell_does_not_call_every_catalogue_books(self):
        repo = pathlib.Path(__file__).resolve().parents[4]
        views = repo / 'plugins/installed/storefront/views'
        offenders = [
            f'{p.relative_to(repo)}'
            for p in views.rglob('*.py')
            if _BOOK_LABEL.search(p.read_text(errors='ignore'))
        ]
        self.assertEqual(offenders, [], f"'All books' hardcoded in the shell: {offenders}")


class StoreIdentityHelperTests(TestCase):
    def _settings(self, **fields):
        from core.models import StoreSettings

        obj = StoreSettings.objects.first() or StoreSettings()
        for key, value in fields.items():
            setattr(obj, key, value)
        obj.save()
        return obj

    def test_store_name_comes_from_settings(self):
        self._settings(store_name='Supernatural Shop')
        self.assertEqual(store_name(), 'Supernatural Shop')

    def test_store_name_never_returns_empty(self):
        self._settings(store_name='')
        name = store_name()
        self.assertTrue(name)
        # Mid-sentence everywhere, so the fallback must not read as a proper
        # noun: "About This shop." was the first attempt.
        self.assertEqual(name, name.lower())

    def test_blurb_is_empty_when_the_merchant_wrote_none(self):
        # Empty on purpose: the seo fallback chain writes a better description
        # from the page than the shell can invent, and an invented one is how a
        # bookshop's copy reached a travel marketplace.
        self._settings(meta_description='', store_description='')
        self.assertEqual(store_blurb(), '')

    def test_blurb_prefers_what_the_merchant_typed(self):
        self._settings(meta_description='', store_description='Small-batch botanical oils.')
        self.assertEqual(store_blurb(), 'Small-batch botanical oils.')

    def test_catalogue_label_follows_the_vertical(self):
        from django.core.cache import cache

        from plugins.registry import app_registry

        if app_registry.is_active('book_product'):
            self.assertEqual(catalogue_label(), 'All books')
            app_registry.deactivate('book_product')
            cache.clear()
            self.addCleanup(cache.clear)
            self.addCleanup(app_registry.activate, 'book_product')
        self.assertEqual(catalogue_label(), 'All products')


class LivePageDescriptionTests(TestCase):
    """The pages that shipped the leak, rendered."""

    def test_content_pages_describe_this_store(self):
        from core.models import StoreSettings

        obj = StoreSettings.objects.first() or StoreSettings()
        obj.store_name = 'Supernatural Shop'
        obj.save()
        # The HEAD only. The active theme in tests IS dot_books, whose own
        # visible copy says "dot books" and should — a theme describing its own
        # shop is not a leak. What leaked was the SHELL's meta description,
        # which every theme inherits.
        for path in ('/about/', '/contact/', '/shipping/'):
            with self.subTest(path=path):
                body = self.client.get(path).content.decode()
                description = re.search(
                    r'<meta name="description" content="([^"]*)"', body, re.I
                )
                self.assertIsNotNone(description, f'{path} has no meta description')
                self.assertNotIn('dot books', description.group(1).lower())

    def test_the_shipping_page_promises_no_rate_it_cannot_source(self):
        # "free over $40" was published on stores with no such rule.
        body = self.client.get('/shipping/').content.decode()
        description = re.search(r'<meta name="description" content="([^"]*)"', body, re.I)
        if description:
            self.assertNotIn('$', description.group(1))
            self.assertNotIn('free over', description.group(1).lower())
