"""The restored slots must actually put plugin markup on the page.

Parity (``test_slot_parity``) proves a slot has *somewhere* to render. This
proves the render actually reaches the response — and, per the ADR 0023 litmus,
that it disappears when the owning plugin is disabled.

``global_head`` is the sharpest case: brand_kit's design tokens are "the palette
and typography the rest of the surface runs on", and until v0.36 they reached
the browser not at all, because ``base.html`` emitted only ``global_below_body``.
"""

from __future__ import annotations

from django.test import TestCase

from plugins.registry import app_registry

#: Emitted by brand_kit/blocks/tokens.html — specific to the contribution, so
#: the assertion fails if the slot stops rendering. A generic check ('<style' in
#: head) passes on the theme's own inline CSS and proves nothing.
_BRAND_TOKENS_MARKER = 'id="morpheus-brand-tokens"'


class GlobalHeadRenderTests(TestCase):
    def _head(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode().split('</head>')[0]

    def test_brand_kit_tokens_reach_the_head(self):
        # The design tokens are "the palette and typography the rest of the
        # surface runs on" — before v0.36 they reached the browser not at all.
        self.assertIn(_BRAND_TOKENS_MARKER, self._head())

    def test_head_slot_is_disable_safe(self):
        """Disabling brand_kit must remove its head contribution (ADR 0023)."""
        self.assertIn(_BRAND_TOKENS_MARKER, self._head())
        app_registry.deactivate('brand_kit')
        try:
            self.assertNotIn(_BRAND_TOKENS_MARKER, self._head())
        finally:
            app_registry.activate('brand_kit')
        self.assertIn(_BRAND_TOKENS_MARKER, self._head())
