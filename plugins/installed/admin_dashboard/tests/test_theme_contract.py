"""The dashboard's look in light and dark mode rests on one token block in base.html.

Dark mode used to be written twice (an explicit `data-theme="dark"` block and a
`prefers-color-scheme` copy), and the copies drifted. Native controls never learned
which mode was on, so in dark mode every checkbox, select and scrollbar stayed light.
And an icon name missing from the glyph map renders as an empty circle with no error
(the order page's "Print invoice" did). These guards keep all three fixed.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BASE = (
    Path(settings.BASE_DIR)
    / 'plugins/installed/admin_dashboard/templates/admin_dashboard/base.html'
)


def _base() -> str:
    return BASE.read_text(encoding='utf-8')


class ThemeTokenTests(SimpleTestCase):
    def test_each_colour_token_is_defined_once_for_both_modes(self):
        # light-dark() carries both values in one declaration; a second block
        # for dark mode is the copy that drifts.
        css = _base()
        self.assertEqual(len(re.findall(r'--surface:\s', css)), 1)
        self.assertIn('light-dark(', css)

    def test_native_controls_follow_the_chosen_mode(self):
        css = _base()
        self.assertRegex(css, r':root\s*\{[^}]*color-scheme:\s*light dark')
        self.assertRegex(css, r':root\[data-theme="light"\]\s*\{\s*color-scheme:\s*light')
        self.assertRegex(css, r':root\[data-theme="dark"\]\s*\{\s*color-scheme:\s*dark')
        self.assertIn('accent-color: var(--brand)', css)

    def test_the_page_sits_behind_the_cards_in_both_modes(self):
        # Cards once had the page's own colour in dark mode, held apart by a
        # 4% ring nobody could see.
        css = _base()
        bg = re.search(r'--bg:\s*light-dark\(([^,]+),\s*([^)]+)\)', css)
        surface = re.search(r'--surface:\s*light-dark\(([^,]+),\s*([^)]+)\)', css)
        self.assertIsNotNone(bg)
        self.assertIsNotNone(surface)
        self.assertNotEqual(bg.group(1).strip(), surface.group(1).strip())
        self.assertNotEqual(bg.group(2).strip(), surface.group(2).strip())


class IconGlyphTests(SimpleTestCase):
    def test_every_icon_a_template_names_has_a_glyph(self):
        mapped = set(re.findall(r"'([a-z0-9-]+)':'ri-", _base()))
        root = Path(settings.BASE_DIR)
        missing = set()
        for path in [
            *root.glob('plugins/**/templates/**/*.html'),
            *root.glob('core/**/templates/**/*.html'),
        ]:
            text = re.sub(
                r'<!--.*?-->|{% comment %}.*?{% endcomment %}',
                '',
                path.read_text(errors='ignore'),
                flags=re.S,
            )
            for name in re.findall(r'data-lucide="([a-z0-9-]+)"', text):
                if name not in mapped:
                    missing.add((name, str(path.relative_to(root))))
        self.assertEqual(sorted(missing), [])
