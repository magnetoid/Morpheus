"""settings.list shows no secret (v0.159.0).

It redacted only top-level names with "api_key", "secret", "password" or
"token" in them, so seo's `search_console_key` (a whole service-account key,
`format: password` on the dashboard) came back in full, and so did every MCP
API token, which sits as `token` inside the agent_mcp `public_keys` list.
"""

from __future__ import annotations

import json

from django.test import TestCase

from core.assistant.tools.ecommerce import settings_list_tool
from plugins.models import PluginConfig


def _listed() -> dict:
    return settings_list_tool.invoke({}).output['plugins']


class SettingsListRedactionTests(TestCase):
    def test_a_password_field_in_the_apps_schema_is_redacted_whatever_its_name(self):
        key = json.dumps({'type': 'service_account', 'private_key': 'PEM-BODY-0123456789'})
        PluginConfig.objects.update_or_create(
            plugin_name='seo',
            defaults={'config': {'search_console_key': key, 'search_console_property': 'x'}},
        )
        config = _listed()['seo']['config']
        self.assertNotIn('PEM-BODY', json.dumps(config))
        self.assertNotIn('private_key', json.dumps(config))
        self.assertEqual(config['search_console_property'], 'x')

    def test_a_secret_inside_a_list_is_redacted_and_the_rest_kept(self):
        PluginConfig.objects.update_or_create(
            plugin_name='agent_mcp',
            defaults={
                'config': {'public_keys': [{'label': 'PIM', 'token': 'mcp_live_abcdefghijklmnop'}]}
            },
        )
        (entry,) = _listed()['agent_mcp']['config']['public_keys']
        self.assertEqual(entry['label'], 'PIM')
        self.assertNotIn('abcdefghijklmnop', entry['token'])
