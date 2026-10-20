"""Every dashboard page uses the shell's width (owner, 2026-10-20).

admin_dashboard/base.html gives the content area one width (max-w-screen-2xl).
Pages used to cap their own wrapper, or a card inside it, anywhere from 672 to
1280 pixels, so some screens were narrow and others wide. A page and its cards
never set a max width now; a paragraph, a table cell or an input may, for its
own sake.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_BASE = Path(settings.BASE_DIR)
_EXTENDS_SHELL = re.compile(r'{%\s*extends\s+["\']admin_dashboard/base\.html["\']\s*%}')
_LAYOUT_CAP = re.compile(
    r'<(?:div|section|form|details|article|header|main|aside|nav)\b[^>]*\bclass="[^"]*'
    r'\bmax-w-(?:2xl|3xl|4xl|5xl|6xl|7xl|screen-\w+|\[[^\]"]+\])'
)


def _dashboard_pages() -> list[Path]:
    pages = []
    for root in ('plugins', 'core'):
        for path in sorted((_BASE / root).rglob('templates/**/*.html')):
            if _EXTENDS_SHELL.search(path.read_text(errors='ignore')):
                pages.append(path)
    return pages


class DashboardPageWidthTests(SimpleTestCase):
    def test_no_page_or_card_caps_its_own_width(self):
        offenders = [
            f'{path.relative_to(_BASE)}: {match.group(0)[:90]}'
            for path in _dashboard_pages()
            for match in _LAYOUT_CAP.finditer(path.read_text(errors='ignore'))
        ]
        self.assertEqual(
            offenders,
            [],
            'The dashboard shell sets every page width (admin_dashboard/base.html); '
            'a page or a card never caps its own.',
        )

    def test_the_shell_sets_the_width(self):
        shell = _BASE / 'plugins/installed/admin_dashboard/templates/admin_dashboard/base.html'
        self.assertIn('max-w-screen-2xl', shell.read_text())

    def test_the_scan_sees_the_dashboard(self):
        # A guard that finds no pages would pass while checking nothing.
        self.assertGreater(len(_dashboard_pages()), 150)
