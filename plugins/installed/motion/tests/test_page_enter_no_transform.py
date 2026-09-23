"""The page-enter animation lands on <html>, so it must never animate transform.

``runtime.js`` does ``document.documentElement.classList.add('morpheus-page-enter')``.
A ``transform`` on the root element — even a *filling* animation whose final
keyframe is ``transform: none`` — makes ``<html>`` the containing block for
``position: fixed`` descendants, so the staff admin bar (the one fixed element
in the storefront header stack) scrolls away with the page instead of staying
pinned, leaving a ~32px hole above the sticky store header. Every theme loads
motion through the ``global_head`` slot, so a transform here broke all three
stores at once — but only for signed-in staff, since the admin bar is the fixed
element that exposes it. Opacity-only fade keeps the entrance without the
containing-block side effect.
"""

from __future__ import annotations

import pathlib

from django.conf import settings
from django.test import SimpleTestCase

_MOTION = pathlib.Path(settings.BASE_DIR) / 'plugins' / 'installed' / 'motion'


def _brace_block(text: str, marker: str) -> str:
    """Return the ``{...}`` block that follows ``marker``, brace-balanced
    (keyframes nest from/to blocks, so a non-greedy regex won't do)."""
    start = text.index(marker)
    open_i = text.index('{', start)
    depth = 0
    for i in range(open_i, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[open_i : i + 1]
    return text[open_i:]


class PageEnterAnimationTests(SimpleTestCase):
    def test_page_enter_class_is_applied_to_the_root_element(self):
        """If this ever moves off <html>/<body>, the no-transform rule below
        can be relaxed — so assert the precondition it depends on."""
        js = (_MOTION / 'static' / 'motion' / 'runtime.js').read_text()
        self.assertIn("documentElement.classList.add('morpheus-page-enter')", js)

    def test_root_page_enter_animation_never_animates_transform(self):
        css = (_MOTION / 'templates' / 'motion' / 'blocks' / 'styles.html').read_text()
        # The keyframes the root's .morpheus-page-enter animation plays.
        kf = _brace_block(css, '@keyframes morpheus-fade-in')
        self.assertNotIn(
            'transform',
            kf,
            'morpheus-fade-in runs on <html>; a transform there makes the root '
            'a containing block and breaks position:fixed (admin bar scrolls '
            'away, hole above the sticky header). Keep it opacity-only.',
        )
