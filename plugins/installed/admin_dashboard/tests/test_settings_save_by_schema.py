"""An app's settings panel saves each field as its schema type (v0.173.0).

A list setting rendered as Python's `[60, 1440, 4320]` and saved back as that
text: cart recovery then failed to read its email delays, fell back to its
defaults and ignored the settings it reads after them. The save now reads each
value through `plugins.config_schema.coerce`, as Linda's `settings.set` does.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from plugins.installed.admin_dashboard.views_split.settings import _build_panel_fields
from plugins.models import PluginConfig
from plugins.registry import app_registry

URL = '/dashboard/settings/cart_abandonment/'
AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


class SaveBySchemaTests(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user(
                username='schema-staff', email='schema@x.test', is_staff=True, is_superuser=True
            )
        )
        self.plugin = app_registry.get('cart_abandonment')
        self.addCleanup(self.plugin.invalidate_config_cache)

    def _stored(self):
        return PluginConfig.objects.get(plugin_name='cart_abandonment').config

    def test_a_list_saves_as_a_list_however_it_was_typed(self):
        for typed, stored in (('30, 90', [30, 90]), ('[60, 1440, 4320]', [60, 1440, 4320])):
            resp = self.client.post(URL, {'step_delays_minutes': typed}, **AJAX)
            self.assertEqual(resp.status_code, 200)
            self.assertIn('step_delays_minutes', resp.json()['saved'])
            self.assertEqual(self._stored()['step_delays_minutes'], stored, typed)

    def test_a_list_renders_as_comma_separated_text(self):
        self.plugin.set_config('step_delays_minutes', [60, 1440])
        fields = {
            f['key']: f for f in _build_panel_fields(self.plugin, self.plugin.get_config_schema())
        }
        self.assertEqual(fields['step_delays_minutes']['value'], '60, 1440')

    def test_numbers_and_boxes_read_as_before(self):
        self.client.post(URL, {'abandon_after_minutes': '45', 'require_email': 'on'}, **AJAX)
        self.assertEqual(self._stored()['abandon_after_minutes'], 45)
        self.assertIs(self._stored()['require_email'], True)
        # A number the field cannot read leaves the stored one alone.
        resp = self.client.post(URL, {'abandon_after_minutes': 'soon'}, **AJAX)
        self.assertNotIn('abandon_after_minutes', resp.json()['saved'])
        self.assertEqual(self._stored()['abandon_after_minutes'], 45)
