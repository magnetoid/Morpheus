"""A closed cart drawer is really closed, in every theme.

Each theme's drawer styles `#cart-drawer { display: flex }`, which beats the
browser's own `[hidden] { display: none }`. So the "closed" drawer stayed on
the page just past the right edge: its shadow showed as a strip on every
storefront page, and Tab still walked into its buttons although it was marked
aria-hidden (found in the partner-portal visual pass, 2026-10-11).

Hiding it again needs a second half: when `open()` unhides the drawer and adds
the open class in the same frame, the browser has no closed position to slide
from and the drawer simply appears. Reading the drawer's layout once after
unhiding commits that position, so the slide-in still animates.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_THEMES = Path(settings.BASE_DIR) / 'themes' / 'library'


def _drawers() -> list[Path]:
    return sorted(_THEMES.glob('*/templates/storefront/_cart_drawer.html'))


class CartDrawerHiddenTests(SimpleTestCase):
    def test_every_theme_has_a_drawer_to_check(self):
        self.assertGreaterEqual(len(_drawers()), 4)

    def test_a_hidden_drawer_is_not_displayed(self):
        for path in _drawers():
            with self.subTest(theme=path.parts[-4]):
                self.assertIn('#cart-drawer[hidden] { display: none; }', path.read_text())

    def test_opening_commits_the_closed_position_before_sliding(self):
        for path in _drawers():
            with self.subTest(theme=path.parts[-4]):
                src = path.read_text()
                unhide = src.index('    drawer.hidden = false;\n')
                reflow = src.index('void drawer.offsetWidth;', unhide)
                slide = src.index("drawer.classList.add('is-shown')", unhide)
                self.assertLess(reflow, slide)
