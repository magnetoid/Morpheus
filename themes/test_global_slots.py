"""Every theme's base template emits the global slots.

The consent banner, the analytics beacon, the ad pixels, the PWA manifest,
the chat widget and the WebMCP tools all arrive through ``global_below_body``;
brand tokens and feed links through ``global_head``; the GDPR links through
``footer_legal``. A theme that forgets one of them silently ships a store
without them — montenegro did, for every global slot, until v0.91.0: a live
bilingual store with no cookie banner. ``core/tests/test_slot_parity.py``
checks only the active theme (dot_books in tests), so this guard reads every
theme's base template on disk, plus the storefront fallback base.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from themes.registry import theme_registry

REQUIRED = ('global_head', 'global_below_body', 'footer_legal', 'footer_extra')
_EMIT = {slot: re.compile(r'storefront_blocks\s+["\']' + slot + r'["\']') for slot in REQUIRED}


def _bases() -> dict[str, Path]:
    bases: dict[str, Path] = {}
    for theme in theme_registry.all_themes():
        candidate = Path(theme.templates_dir) / 'storefront' / 'base.html'
        if candidate.exists():
            bases[theme.name] = candidate
    bases['storefront (fallback)'] = (
        Path(settings.BASE_DIR)
        / 'plugins'
        / 'installed'
        / 'storefront'
        / 'templates'
        / 'storefront'
        / 'base.html'
    )
    return bases


class GlobalSlotsTests(SimpleTestCase):
    def test_every_base_template_emits_the_global_slots(self):
        bases = _bases()
        self.assertGreaterEqual(len(bases), 4, bases)
        for name, path in bases.items():
            source = path.read_text(encoding='utf-8')
            for slot, pattern in _EMIT.items():
                with self.subTest(theme=name, slot=slot):
                    self.assertTrue(
                        pattern.search(source),
                        f'{name}: {path} never emits {{% storefront_blocks "{slot}" %}}',
                    )
