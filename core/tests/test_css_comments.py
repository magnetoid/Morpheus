"""A CSS comment that closes early silently deletes the rule under it.

CSS comments do not nest and end at the first `*/`. The dashboard's icon notes
said "sized to match the Tailwind h-*/w-* the existing markup uses" — the `*/`
inside `h-*/w-*` ended the comment, the rest of the sentence became the selector
of the next rule, and the browser dropped that rule whole: `i[data-lucide] {
display:inline-flex; line-height:1; … }`, the one that centres every dashboard
icon in its box. From 2026-09-23 it never applied, so icons outside buttons and
the sidebar (settings tiles, cards, help marks) sat low and to the right.
Nothing errors: the stylesheet parses, the page renders, a test of the template
passes.

After comments are stripped the way a CSS tokenizer strips them, any `*/` left
over is the tail of a comment that ended too soon.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_SKIP = {'.venv', 'node_modules', 'staticfiles', 'vendor', 'media', 'site', '.janus'}
_STYLE = re.compile(r'<style[^>]*>(.*?)</style>', re.S | re.I)
_COMMENT = re.compile(r'/\*.*?\*/', re.S)


def _css_sources():
    for path in Path(settings.BASE_DIR).rglob('*'):
        if path.suffix not in ('.html', '.css') or '.min.' in path.name:
            continue
        if _SKIP.intersection(path.parts):
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        blocks = _STYLE.findall(text) if path.suffix == '.html' else [text]
        for block in blocks:
            yield path, block


class CssCommentsCloseWhereTheyShouldTests(SimpleTestCase):
    def test_no_comment_ends_early(self):
        offenders = []
        for path, css in _css_sources():
            leftover = _COMMENT.sub('', css)
            if '*/' in leftover:
                at = leftover.index('*/')
                snippet = ' '.join(leftover[max(0, at - 60) : at + 2].split())
                offenders.append(f'{path.relative_to(settings.BASE_DIR)}: …{snippet}')
        self.assertEqual(offenders, [], 'a `*/` inside a CSS comment drops the rule after it')
