"""Linda platform-ops tools — updates, settings.set, plugins.toggle (gated).

Tool.invoke re-raises ToolError (it does not wrap it), so gate failures are
asserted with assertRaises.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

from unittest.mock import patch

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

        with self.assertRaises(ToolError):
            updates_apply_tool.invoke({'confirmed': True})  # missing ack/echo

    def test_apply_calls_guarded_updater(self):
        from core.assistant.tools.admin_ops import updates_apply_tool

        with patch(
            'core.updates.apply_platform_update', return_value={'status': 'applied', 'to': 'v2'}
        ) as ap:
            r = updates_apply_tool.invoke(
                {
                    'confirmed': True,
                    'hard_gate_ack': 'YES',
                    'echo': 'platform update',
                }
            )
        ap.assert_called_once_with(confirm=True)
        self.assertEqual(r.output['status'], 'applied')


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
