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

from plugins.registry import app_registry

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
        # `reviews` ships active in MORPHEUS_DEFAULT_APPS.
        self.assertEqual(self._render('reviews'), 'YES')

    def test_disabled_plugin_is_false(self):
        was_active = 'reviews' in app_registry._active
        app_registry._active.discard('reviews')
        try:
            self.assertEqual(self._render('reviews'), 'NO')
        finally:
            if was_active:
                app_registry._active.add('reviews')

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

        from plugins.registry import app_registry

        pages = {(pg.plugin, pg.label): pg for pg in app_registry.dashboard_pages()}
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
        self.addCleanup(app_registry.activate, self.PLUGIN)

    def test_reenable_restores_contributions_without_restart(self):
        # Baseline: active with a settings panel registered.
        app_registry.activate(self.PLUGIN)
        self.assertIn(self.PLUGIN, app_registry._active)
        self.assertIsNotNone(app_registry.settings_panel(self.PLUGIN))

        # Disable drops the contributions (panel disappears).
        app_registry.deactivate(self.PLUGIN)
        self.assertNotIn(self.PLUGIN, app_registry._active)
        self.assertIsNone(app_registry.settings_panel(self.PLUGIN))

        # Re-enable brings them straight back — no restart.
        self.assertTrue(app_registry.activate(self.PLUGIN))
        self.assertIn(self.PLUGIN, app_registry._active)
        self.assertIsNotNone(app_registry.settings_panel(self.PLUGIN))

    def test_activate_is_idempotent_no_duplicate_panels(self):
        app_registry.activate(self.PLUGIN)
        before = len(app_registry._storefront_blocks)
        # Activating an already-active plugin must not re-collect contributions.
        self.assertTrue(app_registry.activate(self.PLUGIN))
        self.assertEqual(len(app_registry._storefront_blocks), before)

    def test_activate_unknown_plugin_returns_false(self):
        self.assertFalse(app_registry.activate('does_not_exist'))


class ProductShellContributionGuards(TestCase):
    """The products list/form shell must carry NO direct bookvault reference —
    its column, fulfilment card, and bulk action arrive via
    PRODUCT_LIST_COLUMNS / PRODUCT_FORM_CARDS contributions, which the bus
    drops when the plugin is inactive (ADR 0023). A direct reference is
    exactly the leak this repaid: the column survived disable-while-configured
    and a boot-disabled bookvault NoReverseMatch-500'd the product list."""

    SHELL_FILES = (
        'templates/admin_dashboard/products.html',
        'templates/admin_dashboard/product_form.html',
        'views_split/products.py',
    )
    # Load-bearing coupling tokens (imports, URL namespace, shell state) —
    # prose mentions in comments are fine, these are not.
    FORBIDDEN = (
        'plugins.installed.bookvault',
        'bookvault:',
        'bv_authed',
        'bv_links',
        'bv_locations',
        'bv_bulk_link_url',
    )

    def test_products_shell_free_of_bookvault(self):
        base = Path(settings.BASE_DIR) / 'plugins/installed/admin_dashboard'
        for rel in self.SHELL_FILES:
            text = (base / rel).read_text(encoding='utf-8').lower()
            for token in self.FORBIDDEN:
                self.assertNotIn(token, text, f'{rel} couples to bookvault via {token!r}')


class ProtectedAppGuardTests(TestCase):
    """One source of truth for "this app may not be disabled".

    There used to be two hardcoded lists with the same name and different
    contents — `core.safety.PROTECTED_PLUGINS` (gating Linda's disable tools)
    and a frozenset inside admin_dashboard (gating the merchant's toggle).
    They had already drifted: the dashboard refused catalog/orders/payments/
    morpheus_brain while the AI path allowed all four, so the automated path
    was *looser* than the human one.
    """

    def test_no_surface_can_disable_a_soft_bricking_app(self):
        from core.safety import is_plugin_protected
        from plugins.installed.admin_dashboard.views_split.apps import is_protected

        for name in (
            'admin_dashboard',
            'agent_core',
            'rbac',
            'customers',
            'catalog',
            'orders',
            'payments',
            'morpheus_brain',
        ):
            self.assertTrue(is_plugin_protected(name), f'{name}: AI disable tools would allow it')
            self.assertTrue(is_protected(name), f'{name}: merchant dashboard would allow it')

    def test_an_app_can_protect_itself_via_its_manifest(self):
        """The floor is a minimum, not the whole list — a manifest can add."""
        from core.safety import is_plugin_protected
        from plugins.base import MorpheusPlugin
        from plugins.registry import app_registry

        class Probe(MorpheusPlugin):
            name = 'protected_flag_probe'
            label = 'Protected Flag Probe'
            version = '1.0.0'
            protected = True

        self.assertFalse(is_plugin_protected('protected_flag_probe'))  # not registered yet
        app_registry._classes['protected_flag_probe'] = Probe
        try:
            self.assertTrue(is_plugin_protected('protected_flag_probe'))
        finally:
            del app_registry._classes['protected_flag_probe']

    def test_system_apps_are_hidden_from_the_catalogue(self):
        from plugins.installed.admin_dashboard.views_split.apps import is_system

        self.assertTrue(is_system('agent_core'), 'agent_core is surfaced as Linda, not as an app')
        self.assertFalse(is_system('storefront'))
