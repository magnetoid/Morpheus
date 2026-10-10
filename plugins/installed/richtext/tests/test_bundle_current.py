"""The served editor bundle carries the loader fixes from editor.js.

Production has no Node, so ``static/richtext/lexical-editor.bundle.js`` is
built by hand from ``frontend/editor.js`` and committed (frontend/README.md).
A fix in the source that never reached the bundle changes nothing on a live
store: the editor showed imported supplier copy (paragraphs with bare text
lines between them, left by a sanitiser that dropped their tables) as one
run-on line, or empty, until the loader learned to turn top-level text into
paragraphs (2026-10-10).
"""

from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase

_APP = Path(__file__).resolve().parents[1]


class BundleCurrentTests(SimpleTestCase):
    def test_the_bundle_turns_top_level_text_into_paragraphs(self):
        source = (_APP / 'frontend' / 'editor.js').read_text(encoding='utf-8')
        bundle = (_APP / 'static' / 'richtext' / 'lexical-editor.bundle.js').read_text(
            encoding='utf-8'
        )
        marker = 'SECTION|ARTICLE'  # the block-tag pattern survives minification
        self.assertIn(marker, source)
        self.assertIn(marker, bundle, 'rebuild the bundle: cd frontend && npm run build')
