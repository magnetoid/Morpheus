"""Contribution-taxonomy enforcement (UX audit P0#2 + P4).

Eight plugins shipped SettingsPanels in categories that don't exist
(``checkout``, ``content``, ``security``, ``customers``, ``storefront``) —
each panel was invisible on the settings hub and its category URL 404'd,
with no error anywhere. The ``morpheus.E001``/``E002`` system check makes
that class of bug fail ``manage.py check``; these tests pin the check's
behaviour and prove the remapped panels actually render.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils.html import escape

from morpheus.app import DashboardPage, SettingsPanel
from plugins.installed.admin_dashboard.checks import check_contribution_taxonomy
from plugins.registry import app_registry


class TaxonomyCheckTests(TestCase):
    def test_live_registry_is_clean(self):
        """Every registered plugin's panel category + page nav is valid."""
        self.assertEqual(check_contribution_taxonomy(), [])

    def test_unknown_settings_category_is_an_error(self):
        panel = SettingsPanel(
            label='Bad panel', schema={}, plugin='_taxonomy_test', category='not-a-category'
        )
        app_registry._settings_panels['_taxonomy_test'] = panel
        try:
            errors = check_contribution_taxonomy()
        finally:
            app_registry._settings_panels.pop('_taxonomy_test', None)
        self.assertTrue(any(e.id == 'morpheus.E001' for e in errors))

    def test_old_category_slugs_are_aliased_not_errors(self):
        # `taxes`, `security`, `checkout`, … were categories (or the bug that
        # made panels invisible); they now land in the category that took over.
        panel = SettingsPanel(
            label='Old slug', schema={}, plugin='_taxonomy_test', category='taxes'
        )
        app_registry._settings_panels['_taxonomy_test'] = panel
        try:
            errors = check_contribution_taxonomy()
        finally:
            app_registry._settings_panels.pop('_taxonomy_test', None)
        self.assertEqual(errors, [])

    def test_unlisted_section_is_a_warning(self):
        # A listed page whose section is no sidebar section would be in no
        # menu. A warning, not an error: an out-of-tree app must not stop a
        # boot (check errors abort migrate) — the suite holds in-tree at zero.
        page = DashboardPage(
            label='Lost page',
            slug='lost',
            view='plugins.installed.admin_dashboard.views_split.home.home',
            plugin='_taxonomy_test',
            section='not-a-section',
        )
        app_registry._dashboard_pages.append(page)
        try:
            ids = [e.id for e in check_contribution_taxonomy()]
        finally:
            app_registry._dashboard_pages.remove(page)
        self.assertEqual(ids, ['morpheus.W003'])

    def test_card_on_a_landing_without_cards_is_a_warning(self):
        from morpheus.app import DashboardCard

        card = DashboardCard(
            section='seo', title='Nowhere', data=lambda request: {}, plugin='_taxonomy_test'
        )
        app_registry._dashboard_cards.append(card)
        try:
            ids = [e.id for e in check_contribution_taxonomy()]
        finally:
            app_registry._dashboard_cards.remove(card)
        self.assertEqual(ids, ['morpheus.W005'])

    def test_unknown_nav_is_an_error(self):
        page = DashboardPage(
            label='Bad page',
            slug='bad',
            view='plugins.installed.admin_dashboard.views_split.home.home',
            plugin='_taxonomy_test',
            nav='marketplace',
        )
        app_registry._dashboard_pages.append(page)
        try:
            errors = check_contribution_taxonomy()
        finally:
            app_registry._dashboard_pages.remove(page)
        self.assertTrue(any(e.id == 'morpheus.E002' for e in errors))


class RemappedPanelsRenderTests(TestCase):
    """The 8 remapped panels must actually appear on their category pages."""

    def setUp(self):
        self.client = Client()
        staff = get_user_model().objects.create_user(
            username='taxstaff', email='taxstaff@x.test', password='pw', is_staff=True
        )
        self.client.force_login(staff)

    def _panel_labels(self, *plugin_names) -> list[str]:
        """Panel labels as they appear in rendered HTML (auto-escaped —
        'Brand voice & AI content' renders as 'Brand voice &amp; AI content')."""
        labels = []
        for name in plugin_names:
            panel = app_registry.settings_panel(name)
            self.assertIsNotNone(panel, f'{name} should contribute a SettingsPanel')
            labels.append(escape(panel.label))
        return labels

    def test_payments_category_shows_checkout_panels(self):
        resp = self.client.get('/dashboard/settings/payments/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        for label in self._panel_labels(
            'agentic_checkout', 'one_click', 'post_checkout_upsell', 'returns_portal'
        ):
            self.assertIn(label, html)

    def test_remaining_remaps_land_on_their_pages(self):
        # Where the five panels live since the v0.81.0 re-filing
        # (docs/plans/dashboard-hubs-2026-10.md).
        for url, plugin_name in [
            ('/dashboard/settings/storefront/', 'journal'),
            ('/dashboard/settings/payments/', 'fraud_rules'),
            ('/dashboard/settings/marketing/', 'post_purchase'),
            ('/dashboard/settings/storefront/', 'trust_signals'),
            ('/dashboard/settings/team/', 'staff_sso'),
        ]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            (label,) = self._panel_labels(plugin_name)
            self.assertIn(label, resp.content.decode(), f'{plugin_name} panel on {url}')

    def test_ai_page_renders_sibling_ai_panels(self):
        """settings_ai used to hardcode ai_content; ai_stylist's panel was
        invisible everywhere. Both must render now."""
        resp = self.client.get('/dashboard/settings/ai/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        for label in self._panel_labels('ai_content', 'ai_stylist'):
            self.assertIn(label, html)

    def test_gift_cards_canonical_url_resolves(self):
        pages = [p for p in app_registry.dashboard_pages() if p.plugin == 'gift_cards']
        self.assertEqual(pages[0].url, '/dashboard/gift-cards/')
        resp = self.client.get('/dashboard/gift-cards/')
        self.assertEqual(resp.status_code, 200)
