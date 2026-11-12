"""No theme writes a return window into its templates, nor another store's name.

A return window is a promise the returns app keeps, so a page states it from
`return_window_days` (returns_portal's context processor). Until November 2026
dot books and Supernatural printed "30-day returns" whatever the merchant set, and
Irving's journal still called itself "Supernatural Shop" in its AMP titles,
article authors and category description.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase

_COMMENTS = re.compile(r'{%\s*comment\s*%}.*?{%\s*endcomment\s*%}|{#.*?#}', re.S)
_WINDOW = re.compile(r'\b\d+[- ]day\s+returns?\b|\b\d+\s+days\s+to\s+return\b', re.I)
_ROOT = Path(settings.BASE_DIR) / 'themes' / 'library'


class ReturnClaimsTests(SimpleTestCase):
    def test_no_theme_hardcodes_a_return_window(self):
        found = []
        for path in _ROOT.glob('*/templates/**/*.html'):
            text = _COMMENTS.sub('', path.read_text())
            found += [f'{path.relative_to(_ROOT)}: {m.group(0)!r}' for m in _WINDOW.finditer(text)]
        self.assertEqual(found, [], 'State the window from return_window_days.')

    def test_no_theme_names_another_store(self):
        names = {
            'dot_books': ('Supernatural', 'Irving Survival', 'Montenegro'),
            'supernatural_shop': ('dot books', 'dotbooks', 'Irving Survival'),
            'irving_survival': ('Supernatural', 'dot books', 'dotbooks'),
        }
        found = []
        for theme, others in names.items():
            for path in (_ROOT / theme / 'templates').glob('**/*.html'):
                text = _COMMENTS.sub('', path.read_text())
                found += [f'{theme}/{path.name}: {o}' for o in others if o in text]
        self.assertEqual(found, [], 'A theme names its own store through STORE_NAME.')


class ReturnWindowContextTests(TestCase):
    def _days(self):
        from plugins.installed.returns_portal.context_processors import return_window

        return return_window(None)['return_window_days']

    def _set(self, value):
        from plugins.registry import app_registry

        app_registry.get('returns_portal').set_config('return_window_days', value)

    def test_an_untouched_store_states_the_documented_30_days(self):
        self.assertEqual(self._days(), 30)

    def test_the_merchants_window_is_stated(self):
        self._set(14)
        self.assertEqual(self._days(), 14)

    def test_no_returns_hides_the_line(self):
        self._set(0)
        self.assertEqual(self._days(), 0)
        line = Template(
            '{% if return_window_days %}{{ return_window_days }}-day returns{% endif %}'
        ).render(Context({'return_window_days': self._days()}))
        self.assertEqual(line, '')
