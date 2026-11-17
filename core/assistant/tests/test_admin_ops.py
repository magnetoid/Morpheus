"""Linda platform-ops tools — updates, settings.set, plugins.toggle (gated).

Tool.invoke re-raises ToolError (it does not wrap it), so gate failures are
asserted with assertRaises.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from core.assistant.tools.filesystem import ToolError


class SettingsSetTests(TestCase):
    def test_requires_confirmation(self):
        from core.assistant.tools.admin_ops import settings_set_tool

        with self.assertRaises(ToolError):
            settings_set_tool.invoke({'plugin': 'storefront', 'key': 'k', 'value': 'v'})

    def test_writes_and_coerces(self):
        from core.assistant.tools.admin_ops import settings_set_tool
        from plugins.registry import app_registry

        settings_set_tool.invoke(
            {'plugin': 'storefront', 'key': 'lazy_load_images', 'value': 'true', 'confirmed': True}
        )
        self.assertIs(app_registry.get('storefront').get_config().get('lazy_load_images'), True)

    def test_unknown_plugin_errors(self):
        from core.assistant.tools.admin_ops import settings_set_tool

        with self.assertRaises(ToolError):
            settings_set_tool.invoke(
                {'plugin': 'nope', 'key': 'k', 'value': 'v', 'confirmed': True}
            )


class SettingsSetBySchemaTests(TestCase):
    """settings.set reads and checks a value by the app's schema (v0.173.0)."""

    def _set(self, plugin, key, value):
        from core.assistant.tools.admin_ops import settings_set_tool
        from plugins.registry import app_registry

        self.addCleanup(app_registry.get(plugin).invalidate_config_cache)
        return settings_set_tool.invoke(
            {'plugin': plugin, 'key': key, 'value': value, 'confirmed': True}
        )

    def _stored(self, plugin):
        from plugins.models import PluginConfig

        row = PluginConfig.objects.filter(plugin_name=plugin).first()
        return row.config if row else {}

    def test_a_value_is_stored_as_its_declared_type(self):
        self._set('janus', 'turn_timeout_s', '120')
        self._set('janus', 'reasoning_effort', 'high')
        self._set('cart_abandonment', 'step_delays_minutes', '30, 90')
        self.assertEqual(self._stored('janus')['turn_timeout_s'], 120)
        self.assertEqual(self._stored('janus')['reasoning_effort'], 'high')
        self.assertEqual(self._stored('cart_abandonment')['step_delays_minutes'], [30, 90])

    def test_a_value_that_does_not_fit_is_refused_and_nothing_changes(self):
        for key, value, reason in (
            ('turn_timeout_s', '5', "'turn_timeout_s' must be >= 10"),
            ('turn_timeout_s', 'ten', "'turn_timeout_s' must be a whole number"),
            ('reasoning_effort', 'extreme', "'reasoning_effort' must be one of"),
        ):
            with self.assertRaisesMessage(ToolError, reason):
                self._set('janus', key, value)
        with self.assertRaisesMessage(ToolError, "'step_delays_minutes[0]' must be >= 1"):
            self._set('cart_abandonment', 'step_delays_minutes', '0')
        self.assertEqual(self._stored('janus'), {})
        self.assertEqual(self._stored('cart_abandonment'), {})

    def test_where_models_and_credentials_go_stays_the_merchants(self):
        for plugin, key in (
            ('janus', 'base_url'),
            ('janus', 'api_key'),
            ('janus', 'model_source'),
            ('janus', 'provider'),
            ('janus', 'model'),
            ('janus', 'extra_instructions'),
            ('ai_assistant', 'openai_base_url'),
            # ai_assistant reads a base URL for these too but declares none.
            ('ai_assistant', 'gemini_base_url'),
            ('ai_assistant', 'anthropic_base_url'),
            ('openai_shopping', 'push_endpoint'),
            ('backups', 'backup_dir'),
            ('rbac', 'enforcement_mode'),
            ('agent_core', 'spend_cap_daily'),
            ('staff_sso', 'oidc_issuer'),
            ('payments', 'stripe_secret_key'),
        ):
            with self.assertRaisesMessage(ToolError, 'Only the merchant can change'):
                self._set(plugin, key, 'https://elsewhere.example')
            self.assertNotIn(key, self._stored(plugin))

    def test_an_undeclared_key_is_stored_as_before_with_a_warning(self):
        result = self._set('storefront', 'p7_probe_count', '7')
        self.assertEqual(self._stored('storefront')['p7_probe_count'], 7)
        self.assertEqual(len(result.output['warnings']), 1)

    def test_an_undeclared_key_named_like_a_secret_is_refused(self):
        with self.assertRaisesMessage(ToolError, 'Only the merchant can change'):
            self._set('storefront', 'p7_access_token', 'abc')


class SettingsDescribeTests(TestCase):
    def _describe(self, plugin=''):
        from core.assistant.tools.ecommerce import settings_describe_tool

        return settings_describe_tool.invoke({'plugin': plugin} if plugin else {}).output

    def test_without_an_app_it_lists_the_apps_that_have_settings(self):
        apps = {a['plugin']: a for a in self._describe()['apps']}
        self.assertIn('janus', apps)
        self.assertGreater(apps['janus']['settings'], 5)

    def test_each_setting_says_what_it_takes_and_whether_an_agent_may_change_it(self):
        from plugins.registry import app_registry

        janus = app_registry.get('janus')
        self.addCleanup(janus.invalidate_config_cache)
        janus.set_config('api_key', 'sk-live-0123456789')
        out = self._describe('janus')
        settings = {s['key']: s for s in out['settings']}
        self.assertEqual(settings['turn_timeout_s']['minimum'], 10)
        self.assertEqual(settings['turn_timeout_s']['maximum'], 300)
        self.assertEqual(settings['reasoning_effort']['enum'], ['low', 'medium', 'high'])
        self.assertTrue(settings['web_search']['agent_writable'])
        self.assertFalse(settings['base_url']['agent_writable'])
        self.assertTrue(settings['api_key']['secret'])
        self.assertTrue(settings['api_key']['stored'])
        self.assertNotIn('0123456789', json.dumps(out))

    def test_an_unknown_app_is_an_error(self):
        with self.assertRaises(ToolError):
            self._describe('nope')


class PluginsToggleTests(TestCase):
    def test_protected_disable_refused(self):
        from core.assistant.tools.admin_ops import plugins_toggle_tool

        with self.assertRaises(ToolError) as cm:
            plugins_toggle_tool.invoke(
                {
                    'plugin': 'admin_dashboard',
                    'enabled': False,
                    'confirmed': True,
                    'hard_gate_ack': 'YES',
                    'echo': 'admin_dashboard',
                }
            )
        self.assertIn('protected', str(cm.exception).lower())

    def test_enable_non_protected_with_gate(self):
        from core.assistant.tools.admin_ops import plugins_toggle_tool
        from plugins.models import PluginConfig

        r = plugins_toggle_tool.invoke(
            {
                'plugin': 'reviews',
                'enabled': True,
                'confirmed': True,
                'hard_gate_ack': 'YES',
                'echo': 'reviews',
            }
        )
        self.assertTrue(r.output['enabled'])
        self.assertTrue(PluginConfig.objects.get(plugin_name='reviews').is_enabled)

    def test_hard_gate_required(self):
        from core.assistant.tools.admin_ops import plugins_toggle_tool

        with self.assertRaises(ToolError):
            plugins_toggle_tool.invoke({'plugin': 'reviews', 'enabled': True, 'confirmed': True})


class UpdatesToolsTests(TestCase):
    def test_status_reports(self):
        from core.assistant.tools.admin_ops import updates_status_tool

        with (
            patch(
                'core.updates.platform_update_status',
                return_value={'available': 'yes', 'current': 'abc', 'behind': 3},
            ),
            patch('core.versioning.component_versions', return_value={'core': '1.0'}),
        ):
            r = updates_status_tool.invoke({})
        self.assertEqual(r.output['platform']['available'], 'yes')

    def test_status_reads_the_cached_answer_and_names_what_is_out(self):
        from core.assistant.tools.admin_ops import updates_status_tool

        status = {'available': 'yes', 'latest': 'v9.0.0', 'current': 'v1.0.0'}
        with (
            patch('core.updates.can_self_update', return_value=True),
            patch('core.updates.platform_update_status', return_value=status) as pus,
            patch('core.versioning.component_versions', return_value={'core': '1.0'}),
        ):
            r = updates_status_tool.invoke({})
        pus.assert_called_once_with(fetch=False)
        self.assertIn('v9.0.0 is out', r.display)

    def test_apply_requires_hard_gate(self):
        from core.assistant.tools.admin_ops import updates_apply_tool

        with (
            patch('core.updates.can_self_update', return_value=True),
            self.assertRaises(ToolError),
        ):
            updates_apply_tool.invoke({'confirmed': True})  # missing ack/echo

    def test_apply_calls_guarded_updater(self):
        from core.assistant.tools.admin_ops import updates_apply_tool

        with (
            patch('core.updates.can_self_update', return_value=True),
            patch(
                'core.updates.apply_platform_update', return_value={'status': 'applied', 'to': 'v2'}
            ) as ap,
        ):
            r = updates_apply_tool.invoke(
                {
                    'confirmed': True,
                    'hard_gate_ack': 'YES',
                    'echo': 'platform update',
                }
            )
        ap.assert_called_once_with(confirm=True)
        self.assertEqual(r.output['status'], 'applied')

    def test_status_on_a_built_image_says_it_updates_on_release(self):
        from core.assistant.tools.admin_ops import updates_status_tool

        status = {'source': 'git', 'available': 'unavailable', 'reason': 'No git metadata.'}
        with (
            patch('core.updates.can_self_update', return_value=False),
            patch('core.updates.platform_update_status', return_value=status),
        ):
            r = updates_status_tool.invoke({})
        self.assertIn('This store cannot update itself', r.display)
        self.assertNotIn('Update unavailable', r.display)
        self.assertEqual(r.output['running']['version'], settings.MORPHEUS_VERSION)
        self.assertFalse(r.output['running']['self_update'])

    def test_status_says_how_a_built_image_takes_the_release(self):
        from core.assistant.tools.admin_ops import updates_status_tool

        status = {
            'source': 'manifest',
            'available': 'yes',
            'latest': 'v9.0.0',
            'image': 'ghcr.io/magnetoid/morpheus:' + 'a' * 40,
            'path': 'manual',
            'breaking': True,
            'migrating_url': 'https://example.test/MIGRATING.md',
        }
        with (
            patch('core.updates.can_self_update', return_value=False),
            patch('core.updates.platform_update_status', return_value=status),
        ):
            r = updates_status_tool.invoke({})
        self.assertIn('MORPHEUS_IMAGE=ghcr.io/magnetoid/morpheus:', r.display)
        self.assertNotIn('updates when a new version is released', r.display)
        self.assertIn('docker compose up -d --no-build', r.display)
        self.assertIn('upgrade steps: https://example.test/MIGRATING.md', r.display)

    def test_status_output_is_plain_json(self):
        # Tool output is stored as JSON (the audit trail, Linda's chat history)
        # with no encoder for dates: a datetime in it loses both records.
        from core.assistant.tools.admin_ops import updates_status_tool
        from core.models import DeployEvent

        status = {'source': 'git', 'available': 'unavailable', 'reason': 'No git metadata.'}
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'pre-deploy'
            folder.mkdir()
            name = f'morpheus-backup-20261019T140200Z-{settings.MORPHEUS_VERSION}-aaaaaaa.tar.gz'
            (folder / name).write_bytes(b'x')
            DeployEvent.objects.create(
                version=settings.MORPHEUS_VERSION,
                commit='a' * 40,
                deployed_at=datetime(2026, 10, 19, 14, 3, tzinfo=UTC),
            )
            with (
                patch.dict(os.environ, {'MORPHEUS_BACKUP_DIR': tmp, 'SOURCE_COMMIT': 'a' * 40}),
                patch('core.updates.can_self_update', return_value=False),
                patch('core.updates.platform_update_status', return_value=status),
            ):
                r = updates_status_tool.invoke({})
        json.dumps(r.output)  # no default=: plain JSON only
        self.assertEqual(r.output['running']['deployed_at'], '2026-10-19T14:03:00+00:00')
        self.assertEqual(r.output['running']['backup']['taken_at'], '2026-10-19T14:02:00+00:00')
        self.assertIn('installed 2026-10-19 14:03 UTC', r.display)
        self.assertIn('the last update that changed it: 2026-10-19 14:02 UTC', r.display)

    def test_apply_on_a_built_image_says_it_cannot_run_here(self):
        from core.assistant.tools.admin_ops import updates_apply_tool

        with (
            patch('core.updates.can_self_update', return_value=False),
            patch('core.updates.apply_platform_update') as ap,
        ):
            r = updates_apply_tool.invoke({})
        ap.assert_not_called()
        self.assertEqual(r.output['status'], 'unavailable')
        self.assertIn("can't update itself", r.display)


class ThemeActivateTests(TestCase):
    def test_hard_gate_required(self):
        from core.assistant.tools.admin_ops import theme_activate_tool

        with self.assertRaises(ToolError):
            theme_activate_tool.invoke({'theme': 'dot_books', 'confirmed': True})

    def test_unknown_theme(self):
        from core.assistant.tools.admin_ops import theme_activate_tool

        with self.assertRaises(ToolError):
            theme_activate_tool.invoke(
                {
                    'theme': 'no_such_theme',
                    'confirmed': True,
                    'hard_gate_ack': 'YES',
                    'echo': 'no_such_theme',
                }
            )

    def test_activate_discovered_theme(self):
        from core.assistant.tools.admin_ops import theme_activate_tool
        from themes.models import ThemeConfig

        r = theme_activate_tool.invoke(
            {
                'theme': 'dot_books',
                'confirmed': True,
                'hard_gate_ack': 'YES',
                'echo': 'dot_books',
            }
        )
        self.assertEqual(r.output['active_theme'], 'dot_books')
        self.assertTrue(ThemeConfig.objects.get(theme_name='dot_books').is_active)


# WorkflowsRunTests moved to plugins/installed/workflows/tests/test_agent_tools.py
# with the tool itself (boundary ratchet).


# OrdersRefundTests moved to plugins/installed/orders/tests/test_agent_tools.py
# with the tool itself (core→plugin boundary refactor, Phase 1). The hard-gate +
# audit are preserved on the migrated orders.refund.
