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
        self.assertIn('This store updates when a new version is released', r.display)
        self.assertNotIn('Update unavailable', r.display)
        self.assertEqual(r.output['running']['version'], settings.MORPHEUS_VERSION)
        self.assertFalse(r.output['running']['self_update'])

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
