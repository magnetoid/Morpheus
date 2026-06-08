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
        '/dashboard/media/': 'media_enabled',
        '/dashboard/book-taxonomies/': 'book_product_enabled',
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

    def test_affiliates_block_is_plugin_guarded(self):
        # Affiliates renders a parent/child block (not a single inline link); it
        # must sit inside a `{% plugin_enabled "affiliates" %}` / `{% if %}` block.
        src = _BASE_HTML.read_text(encoding='utf-8')
        self.assertIn('{% plugin_enabled "affiliates" as affiliates_enabled %}', src)
        self.assertIn('/dashboard/apps/affiliates/list/', src)
