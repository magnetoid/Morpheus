"""The active theme's settings, on a Theme card under Settings, Storefront.

Until v0.185.0 a theme declared settings (`get_config_schema`) that nobody could
change: no dashboard page and no Linda tool wrote them, only the database.
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from themes.registry import theme_registry

# The active theme in tests (dot_books) declares no settings, so each test gives it one.
SCHEMA = {
    'type': 'object',
    'properties': {
        'tagline': {'type': 'string', 'default': 'A quiet shelf', 'title': 'Tagline'},
    },
}

PAGE = '/dashboard/apps/storefront/theme/'


class _Signed(TestCase):
    def setUp(self):
        self.theme = theme_registry.active
        self.theme.invalidate_config_cache()
        self.addCleanup(self.theme.invalidate_config_cache)
        schema = patch.object(type(self.theme), 'get_config_schema', return_value=SCHEMA)
        schema.start()
        self.addCleanup(schema.stop)
        self.admin = get_user_model().objects.create_superuser(
            username='theme-admin', email='theme-admin@example.test', password='pw-12345!'
        )
        self.client.force_login(self.admin)

    def _schema_with(self, **extra):
        schema = self.theme.get_config_schema()
        props = {**schema.get('properties', {}), **extra}
        return patch.object(
            type(self.theme),
            'get_config_schema',
            return_value={'type': 'object', 'properties': props},
        )


class ThemeSettingsPageTests(_Signed):
    def test_the_storefront_settings_list_the_theme_card(self):
        body = self.client.get('/dashboard/settings/storefront/').content.decode()
        self.assertIn(f'href="{PAGE}"', body)
        self.assertIn('Settings your active theme offers', body)

    def test_the_page_shows_the_active_themes_settings(self):
        resp = self.client.get(PAGE)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn(f'Theme: {self.theme.label}', body)
        self.assertIn('name="tagline"', body)

    def test_saving_changes_the_theme_setting(self):
        resp = self.client.post(PAGE, {'tagline': 'A new line'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(theme_registry.active.get_config_value('tagline'), 'A new line')

    def test_an_unticked_switch_turns_off_only_when_the_form_showed_it(self):
        with self._schema_with(show_bar={'type': 'boolean', 'default': True}):
            self.theme.set_config('show_bar', True)
            self.client.post(PAGE, {'tagline': 'x'})
            self.assertIs(self.theme.get_config_value('show_bar'), True)
            self.client.post(PAGE, {'tagline': 'x', '_booleans': 'show_bar'})
            self.assertIs(self.theme.get_config_value('show_bar'), False)

    def test_a_number_that_is_not_one_keeps_its_stored_value(self):
        with self._schema_with(columns={'type': 'integer', 'default': 3}):
            self.theme.set_config('columns', 4)
            self.client.post(PAGE, {'tagline': 'x', 'columns': 'abc'})
            self.assertEqual(self.theme.get_config_value('columns'), 4)
            self.assertEqual(self.theme.get_config_value('tagline'), 'x')

    def test_a_theme_with_no_settings_says_so(self):
        with patch.object(type(self.theme), 'get_config_schema', return_value={}):
            body = self.client.get(PAGE).content.decode()
        self.assertIn(f'The active theme, {self.theme.label}, has no settings.', body)


class ThemeSettingsPermissionTests(TestCase):
    """The page is a settings page: anonymous visitors sign in first, and while
    roles are enforced only a role holding `system.write` may open it."""

    def setUp(self):
        from plugins.installed.rbac.models import Role
        from plugins.registry import app_registry

        Role.ensure_system_roles()
        rbac = app_registry.get('rbac')
        rbac.set_config('enforcement_mode', 'enforce')
        self.addCleanup(rbac.invalidate_config_cache)
        self.addCleanup(rbac.set_config, 'enforcement_mode', 'log')

    def test_anonymous_is_sent_to_sign_in(self):
        resp = self.client.get(PAGE)
        self.assertEqual(resp.status_code, 302)

    def test_staff_without_system_write_is_refused_while_rbac_enforces(self):
        staff = get_user_model().objects.create_user(
            username='no-role', email='no-role@example.test', password='pw-12345!', is_staff=True
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(PAGE).status_code, 403)

    def test_a_superuser_gets_the_page(self):
        admin = get_user_model().objects.create_superuser(
            username='su', email='su@example.test', password='pw-12345!'
        )
        self.client.force_login(admin)
        self.assertEqual(self.client.get(PAGE).status_code, 200)
