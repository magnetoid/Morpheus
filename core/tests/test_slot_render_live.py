"""The restored slots must actually put plugin markup on the page.

Parity (``test_slot_parity``) proves a slot has *somewhere* to render. This
proves the render actually reaches the response — and, per the ADR 0023 litmus,
that it disappears when the owning plugin is disabled.

``global_head`` is the sharpest case: until v0.36 nothing a plugin contributed
there reached the browser at all, because ``base.html`` emitted only
``global_below_body``. motion's animation CSS is the example here (brand_kit's
design tokens were, until the app left in v0.122.0).
"""

from __future__ import annotations

from django.test import TestCase

from plugins.registry import app_registry

#: A contribution-specific marker: motion's animation CSS (`<style id="morpheus-motion-styles"`).
#: A bare '<style' in the head passes on the theme's own inline CSS and proves nothing.
_HEAD_BLOCK_MARKER = 'id="morpheus-motion-styles"'


class GlobalHeadRenderTests(TestCase):
    def _head(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode().split('</head>')[0]

    def test_a_contributed_head_block_reaches_the_head(self):
        self.assertIn(_HEAD_BLOCK_MARKER, self._head())

    def test_head_slot_is_disable_safe(self):
        """Disabling motion must remove its head contribution (ADR 0023)."""
        self.assertIn(_HEAD_BLOCK_MARKER, self._head())
        app_registry.deactivate('motion')
        try:
            self.assertNotIn(_HEAD_BLOCK_MARKER, self._head())
        finally:
            app_registry.activate('motion')
        self.assertIn(_HEAD_BLOCK_MARKER, self._head())
