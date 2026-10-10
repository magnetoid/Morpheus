"""Declarative WebMCP: the storefront forms an agent can drive carry tool names.

Chrome's declarative API turns a form with ``toolname`` / ``tooldescription``
into a tool whose schema is the form's controls; Lighthouse's agentic-browsing
category reports "WebMCP form coverage" only once such forms exist (its Chrome
has no ``modelContext``, so the imperative tools in ``webmcp.py`` are invisible
to it). The vocabulary is fixed here: one name per intent, used by every theme,
never on a template that repeats per product (two forms with one name collide),
and never a name the imperative tools already take.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from plugins.installed.agent_mcp.webmcp import TOOLS

FORM_TOOLS = {
    'search_shop': 'search.html',
    'search_by_description': 'search.html',
    'add_this_product_to_cart': 'product_detail.html',
    'subscribe_to_newsletter': 'base.html',
}
# Templates rendered once per product on a page: a tool name there would repeat.
REPEATING = ('_product_card.html', 'home.html')
_NAME = re.compile(r'toolname="([^"]+)"')


def _themes() -> list[Path]:
    root = Path(settings.BASE_DIR) / 'themes' / 'library'
    return sorted(p for p in root.iterdir() if (p / 'templates' / 'storefront').is_dir())


class DeclarativeFormToolsTests(SimpleTestCase):
    def test_every_theme_names_the_search_add_and_newsletter_forms(self):
        for theme in _themes():
            store = theme / 'templates' / 'storefront'
            for name, template in FORM_TOOLS.items():
                path = store / template
                if not path.exists():
                    continue
                source = path.read_text(encoding='utf-8')
                has_form = (
                    'action="/search/"' in source
                    or 'action="/cart/add/' in source
                    or 'action="/newsletter/subscribe/"' in source
                )
                if not has_form:
                    continue
                if name == 'search_by_description' and 'mood-q' not in source:
                    continue
                with self.subTest(theme=theme.name, tool=name):
                    self.assertEqual(source.count(f'toolname="{name}"'), 1, path)
                    self.assertIn('tooldescription="', source)

    def test_names_are_one_vocabulary_and_never_repeat_on_a_page(self):
        imperative = {t['name'] for t in TOOLS}
        for theme in _themes():
            for path in (theme / 'templates').rglob('*.html'):
                names = _NAME.findall(path.read_text(encoding='utf-8'))
                with self.subTest(template=str(path.relative_to(theme))):
                    self.assertTrue(set(names) <= set(FORM_TOOLS), set(names) - set(FORM_TOOLS))
                    self.assertFalse(set(names) & imperative, 'clashes with an imperative tool')
                    self.assertEqual(
                        len(names), len(set(names)), 'a tool name repeats in one template'
                    )
                    if path.name in REPEATING:
                        self.assertEqual(names, [], f'{path.name} repeats per product')

    def test_annotated_inputs_describe_their_parameter(self):
        for theme in _themes():
            search = theme / 'templates' / 'storefront' / 'search.html'
            if search.exists():
                source = search.read_text(encoding='utf-8')
                with self.subTest(theme=theme.name):
                    self.assertIn('name="q"', source)
                    self.assertIn('toolparamdescription="', source)
