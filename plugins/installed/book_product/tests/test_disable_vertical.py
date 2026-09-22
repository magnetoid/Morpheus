"""A non-book store can switch the book vertical off, and a store that sets
nothing is unaffected.

book_product ships in MORPHEUS_DEFAULT_APPS (the first store sold books), so a
travel/occult store inherits /genres/, /authors/, a "Book taxonomies" dashboard
page and empty book nav it can never fill. MORPHEUS_DISABLED_APPS subtracts it
(with audiobooks + the book-gated eco_impact) from the deployment's app list —
and its nav context processors are contributed, not listed in settings.TEMPLATES,
so a disabled book_product runs none of its code instead of querying unloaded
models every request.
"""

from __future__ import annotations

import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

from plugins.registry import app_registry

_ASSEMBLE = (
    'import django, os; os.environ.setdefault("DJANGO_SETTINGS_MODULE", "morph.settings");'
    'django.setup();'
    'from django.conf import settings as s;'
    'print("\\n".join(a for a in s.ALL_MORPHEUS_APPS if "installed." in a))'
)


def _app_list(**env_overrides) -> list[str]:
    """The real ALL_MORPHEUS_APPS a deployment would boot with, assembled by
    importing settings in a subprocess (settings assemble at import, once)."""
    env = {**os.environ, 'DATABASE_URL': 'sqlite:///:memory:'}
    env.update(env_overrides)
    out = subprocess.run(
        [sys.executable, '-c', _ASSEMBLE], env=env, capture_output=True, text=True, check=True
    )
    return [
        line.split('installed.')[-1] for line in out.stdout.splitlines() if 'installed.' in line
    ]


class DisabledAppsMechanismTests(SimpleTestCase):
    def test_a_store_that_disables_the_vertical_loses_exactly_it(self):
        apps = _app_list(
            MORPHEUS_DISABLED_APPS='plugins.installed.book_product,'
            'plugins.installed.audiobooks,plugins.installed.eco_impact',
            MORPHEUS_EXTRA_APPS='plugins.installed.booking_marketplace',
        )
        self.assertNotIn('book_product', apps)
        self.assertNotIn('audiobooks', apps)
        self.assertNotIn('eco_impact', apps)
        # the store's own vertical and the core spine are untouched
        self.assertIn('booking_marketplace', apps)
        self.assertIn('catalog', apps)
        self.assertIn('orders', apps)

    def test_a_store_that_sets_nothing_keeps_the_vertical(self):
        """dotbooks: no disable env -> book_product and its bundle stay."""
        apps = _app_list()
        self.assertIn('book_product', apps)
        self.assertIn('audiobooks', apps)
        self.assertIn('eco_impact', apps)

    def test_disabling_a_non_default_app_is_a_no_op_not_a_crash(self):
        apps = _app_list(MORPHEUS_DISABLED_APPS='plugins.installed.does_not_exist')
        self.assertIn('book_product', apps)

    def test_an_app_in_both_default_and_extra_is_not_double_registered(self):
        apps = _app_list(MORPHEUS_EXTRA_APPS='plugins.installed.book_product')
        self.assertEqual(apps.count('book_product'), 1)


class BookNavIsContributedNotHardcodedTests(SimpleTestCase):
    """The move that makes a disable clean: if these ever go back into
    settings.TEMPLATES, a disabled book_product runs a removed app's context
    processor against unloaded Genre/Topic models on every request."""

    def test_book_product_context_processors_are_not_in_settings_templates(self):
        cps = settings.TEMPLATES[0]['OPTIONS']['context_processors']
        self.assertFalse(
            any('book_product' in c for c in cps),
            'book_product nav must be contributed via register_context_processor, '
            'not listed in settings.TEMPLATES',
        )

    def test_book_product_registers_its_nav_processors(self):
        owners = {
            getattr(func, '__name__', ''): owner
            for func, owner in app_registry.context_processors()
        }
        self.assertEqual(owners.get('nav_genres'), 'book_product')
        self.assertEqual(owners.get('nav_topics'), 'book_product')


class SharedCardSurvivesBookDisableTests(SimpleTestCase):
    """The shared storefront product card renders on stores with the book
    vertical off (montenegro, supernatural), so it must not `{% load
    book_extras %}` — that lib only exists while book_product is installed, and
    `{% load %}` fails at parse time. `first_sentence` (its only general filter)
    is in core's `morph` now; the book-specific tags stay in book_extras."""

    def test_no_theme_product_card_loads_book_extras(self):
        import pathlib

        root = pathlib.Path(settings.BASE_DIR) / 'themes' / 'library'
        offenders = [
            str(card.relative_to(root))
            for card in root.glob('*/templates/storefront/_product_card.html')
            if 'book_extras' in card.read_text()
        ]
        self.assertEqual(offenders, [], f'shared card loads book_extras: {offenders}')
