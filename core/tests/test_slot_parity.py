"""Every contributed storefront slot must have somewhere to render.

A ``StorefrontBlock(slot='x')`` is silent when no template emits
``{% storefront_blocks "x" %}``: the plugin is enabled, its tests pass, its
block renders correctly in isolation — and the merchant sees nothing. That is
the worst failure mode a contribution system has, because nothing anywhere
reports it.

It had happened four times over by v0.36: ``global_head`` (brand_kit's design
tokens and motion's animation CSS never reached ``<head>``), ``checkout_extra``
(six plugins' checkout surfaces), ``pdp_below_gallery`` (media_3d's 3D/AR viewer,
ugc_reviews' photo strip) and ``account_summary_extra`` (referrals,
returns_portal). CLAUDE.md's rule is that an advisory convention which keeps
getting violated should be promoted to enforcement — this is that enforcement.

Slots are read from the **runtime registry**, not by grepping ``plugin.py``:
dynamics registers one block per entry in ``SLOT_CHOICES`` inside a loop, which
a source grep silently misses.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from plugins.registry import plugin_registry

#: Slots a plugin contributes but the active theme intentionally does not render.
#: Each entry needs a reason — an allow-list without one is just a muted alarm.
_INTENTIONALLY_UNRENDERED = {
    # journal/blocks/post.html is a COMPLETE alternative post renderer (it takes
    # `post` + `blocks`). dot_books renders journal posts itself from `entry`,
    # so emitting this slot would double-render the article — and render it
    # empty, since the theme passes no `post`. The slot exists for themes that
    # would rather the plugin own the page.
    'journal': 'dot_books renders journal posts itself; slot is for other themes',
    # dynamics offers a THEME-AGNOSTIC slot menu (SLOT_CHOICES) and registers a
    # renderer for each entry, so it contributes this even though dot_books
    # deliberately dropped the slot (its editor's-pick hero leads the page).
    # The damaging case — Autopilot auto-provisioning here on every new store —
    # is fixed and pinned by test_merchant_selectable_slots_are_rendered.
    # Residual: a merchant who hand-picks this slot in dot_books still sees
    # nothing; a theme-aware picker would need the menu filtered per theme.
    'home_above_grid': 'theme-agnostic dynamics menu entry; dot_books leads with the hero',
}

_TAG = re.compile(r'storefront_blocks\s+["\']([a-z_]+)["\']')


def _rendered_slots() -> set[str]:
    """Every slot emitted by any template in the project."""
    roots = [Path(settings.BASE_DIR)]
    found: set[str] = set()
    for root in roots:
        for path in root.rglob('*.html'):
            parts = path.parts
            if any(p in ('node_modules', '.venv', 'vendor', 'staticfiles') for p in parts):
                continue
            try:
                found.update(_TAG.findall(path.read_text(encoding='utf-8', errors='ignore')))
            except OSError:
                continue
    return found


def _contributed_slots() -> set[str]:
    return {
        b.slot for b in getattr(plugin_registry, '_storefront_blocks', []) if getattr(b, 'slot', '')
    }


class StorefrontSlotParityTests(SimpleTestCase):
    def test_every_contributed_slot_is_rendered_somewhere(self):
        contributed = _contributed_slots()
        self.assertTrue(contributed, 'no storefront blocks registered — registry not ready?')

        dead = contributed - _rendered_slots() - set(_INTENTIONALLY_UNRENDERED)
        self.assertEqual(
            dead,
            set(),
            'These plugins contribute to slots no template renders, so their surfaces are '
            f'invisible to customers: {sorted(dead)}. Either emit '
            '{% storefront_blocks "<slot>" %} in the theme, or add the slot to '
            '_INTENTIONALLY_UNRENDERED with a reason.',
        )

    def test_allow_list_entries_are_still_contributed(self):
        # A stale allow-list entry hides a slot that no longer exists — the same
        # class of rot the boundary ratchets guard against.
        stale = set(_INTENTIONALLY_UNRENDERED) - _contributed_slots()
        self.assertEqual(stale, set(), f'allow-listed slots no longer contributed: {sorted(stale)}')

    def test_merchant_selectable_slots_are_rendered(self):
        """Slots a MERCHANT can pick in the dashboard must render.

        dynamics offers a slot menu (`SLOT_CHOICES`) and auto-provisions blocks
        on `_DEFAULT_SLOTS`. A menu entry the theme drops means the merchant
        saves a block that never appears — which is exactly what shipped:
        autopilot defaulted to `home_above_grid` while dot_books deliberately
        removed that slot, so every new store got an invisible block.
        """
        from plugins.installed.dynamics.autopilot import _DEFAULT_SLOTS

        unrendered = set(_DEFAULT_SLOTS) - _rendered_slots()
        self.assertEqual(
            unrendered,
            set(),
            f'Autopilot provisions blocks on slots the theme does not render: {sorted(unrendered)}',
        )
