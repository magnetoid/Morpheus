"""Disable-test guards (ADR 0013): a plugin's dashboard surfaces must vanish
when the plugin is disabled — no orphan 404 nav link left behind.

Two layers:
  * the `plugin_enabled` tag (the guard primitive every hardcoded nav link uses)
    correctly reflects registry active-state;
  * every hardcoded, plugin-owned link in the sidebar sits behind that guard —
    a structural check that fails the moment someone adds an UNGUARDED
    `<a href="/dashboard/<plugin-feature>/">`, which is exactly the regression
    this track is closing.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.test import TestCase

from plugins.registry import plugin_registry

_BASE_HTML = (
    Path(settings.BASE_DIR)
    / 'plugins/installed/admin_dashboard/templates/admin_dashboard/base.html'
)


class PluginEnabledTagTests(TestCase):
    def _render(self, slug: str) -> str:
        tpl = Template(
            '{% load morph %}{% plugin_enabled "' + slug + '" as e %}'
            '{% if e %}YES{% else %}NO{% endif %}'
        )
        return tpl.render(Context({})).strip()

    def test_active_plugin_is_true(self):
        # `reviews` ships active in MORPHEUS_DEFAULT_PLUGINS.
        self.assertEqual(self._render('reviews'), 'YES')

    def test_disabled_plugin_is_false(self):
        was_active = 'reviews' in plugin_registry._active
        plugin_registry._active.discard('reviews')
        try:
            self.assertEqual(self._render('reviews'), 'NO')
        finally:
            if was_active:
                plugin_registry._active.add('reviews')

    def test_unknown_plugin_is_false(self):
        self.assertEqual(self._render('no_such_plugin_xyz'), 'NO')


class DashboardNavGuardTests(TestCase):
    """Each hardcoded, plugin-owned nav href must be on a line that also carries
    its `{% if <plugin>_enabled %}` guard, so disabling the plugin removes the
    link. Add a row here whenever a plugin link is hardcoded into base.html."""

    # href fragment  ->  the plugin_enabled guard variable that must gate it
    GUARDED_LINKS = {
        '/dashboard/reviews/': 'reviews_enabled',
        '/dashboard/draft-orders/': 'draft_orders_enabled',
        # About link hardcoded into the top-right user dropdown. (The Version
        # link is guarded by the same `release_notes_on` in the dropdown but is
        # not listed here: the href also appears in the sidebar with a
        # multi-line guard block that this inline check can't match.)
        '/dashboard/apps/release_notes/about/': 'release_notes_on',
    }

    def test_plugin_nav_links_are_guarded(self):
        lines = _BASE_HTML.read_text(encoding='utf-8').splitlines()
        for href, guard in self.GUARDED_LINKS.items():
            hits = [ln for ln in lines if href in ln]
            self.assertTrue(hits, f'{href} not found in base.html — did the nav change?')
            for ln in hits:
                self.assertIn(
                    f'{{% if {guard} %}}',
                    ln,
                    f'UNGUARDED plugin nav link: {href} must be wrapped in '
                    f'{{% if {guard} %}} so it vanishes when the plugin is disabled '
                    f'(ADR 0013 disable test).',
                )

    def test_contributed_nav_is_not_hardcoded(self):
        # Affiliates / media / book_product moved from hardcoded base.html
        # blocks to nav='main' DashboardPage contributions (IA redesign
        # phase 1) — the contributed-sections loop auto-hides a disabled
        # plugin, which is stronger than a template guard. Keep base.html
        # free of them so the two nav systems can't drift apart again.
        src = _BASE_HTML.read_text(encoding='utf-8')
        for fragment in (
            '/dashboard/apps/affiliates/',
            '/dashboard/media/',
            '/dashboard/book-taxonomies/',
        ):
            self.assertNotIn(fragment, src, f'{fragment} is hardcoded again')

        from plugins.registry import plugin_registry

        pages = {(pg.plugin, pg.label): pg for pg in plugin_registry.dashboard_pages()}
        self.assertTrue(
            any(plugin == 'affiliates' for plugin, _ in pages),
            'affiliates contributes no dashboard pages',
        )


class HotEnableTests(TestCase):
    """registry.activate() lights a plugin up at runtime — the mirror of
    deactivate() — so toggling a plugin ON in the dashboard no longer needs a
    web-container restart (the regression behind the audiobooks panel report).
    """

    PLUGIN = 'audiobooks'  # not protected, safe to toggle in a test

    def setUp(self):
        # Always leave the registry as we found it, even if an assertion fails.
        self.addCleanup(plugin_registry.activate, self.PLUGIN)

    def test_reenable_restores_contributions_without_restart(self):
        # Baseline: active with a settings panel registered.
        plugin_registry.activate(self.PLUGIN)
        self.assertIn(self.PLUGIN, plugin_registry._active)
        self.assertIsNotNone(plugin_registry.settings_panel(self.PLUGIN))

        # Disable drops the contributions (panel disappears).
        plugin_registry.deactivate(self.PLUGIN)
        self.assertNotIn(self.PLUGIN, plugin_registry._active)
        self.assertIsNone(plugin_registry.settings_panel(self.PLUGIN))

        # Re-enable brings them straight back — no restart.
        self.assertTrue(plugin_registry.activate(self.PLUGIN))
        self.assertIn(self.PLUGIN, plugin_registry._active)
        self.assertIsNotNone(plugin_registry.settings_panel(self.PLUGIN))

    def test_activate_is_idempotent_no_duplicate_panels(self):
        plugin_registry.activate(self.PLUGIN)
        before = len(plugin_registry._storefront_blocks)
        # Activating an already-active plugin must not re-collect contributions.
        self.assertTrue(plugin_registry.activate(self.PLUGIN))
        self.assertEqual(len(plugin_registry._storefront_blocks), before)

    def test_activate_unknown_plugin_returns_false(self):
        self.assertFalse(plugin_registry.activate('does_not_exist'))
