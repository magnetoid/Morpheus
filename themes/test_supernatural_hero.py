"""Supernatural's hero cover is as large as its window, and tells the browser so.

The CSS sets how wide the cover is drawn; the <img> ``sizes`` attribute tells
the browser which file to fetch for it. The cover grew to fill the column beside
the copy (owner's ask, v0.84.0); a ``sizes`` still naming the old 360px would
make the browser fetch a file half the width it draws, and the larger picture
would come out blurred.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase

_HOME = (
    Path(__file__).resolve().parent
    / 'library'
    / 'supernatural_shop'
    / 'templates'
    / 'storefront'
    / 'home.html'
)


class SupernaturalHeroCoverTests(SimpleTestCase):
    def test_the_desktop_cover_is_large_and_sizes_names_its_widths(self):
        src = _HOME.read_text(encoding='utf-8')
        rule = re.search(
            r'\.window__cover \{ width: min\(100%, clamp\((\d+)px, (\d+)vw, (\d+)px\)\)', src
        )
        self.assertIsNotNone(rule, 'the desktop cover width rule')
        _low, vw, widest = (int(n) for n in rule.groups())
        self.assertGreaterEqual(widest, 560)
        sizes = re.findall(r'sizes="([^"]+)"', src)
        self.assertTrue(sizes)
        for value in sizes:
            with self.subTest(sizes=value):
                self.assertIn(f'{widest}px', value)
                self.assertIn(f'{vw}vw', value)
