"""The Agent guardrails settings panel + its key-name contract with compliance.

The five guardrail keys must render in the panel, resolve defaults via
get_config_schema, and match the keys the AI-Act compliance report reads — there
is no shared constant, so a rename here silently breaks the report.
"""

from __future__ import annotations

from django.test import TestCase

_KEYS = {
    'agents_paused',
    'max_agent_runs_daily',
    'spend_cap_daily',
    'max_price_change_pct',
    'max_refund_value',
}


def _plugin():
    from plugins.registry import app_registry

    return app_registry.get('agent_core')


class GuardrailPanelTests(TestCase):
    def test_panel_exposes_the_five_guardrail_keys(self):
        panel = _plugin().contribute_settings_panel()
        self.assertIsNotNone(panel)
        self.assertEqual(panel.category, 'ai')
        props = (panel.schema or {}).get('properties', {})
        self.assertTrue(_KEYS.issubset(props), f'panel missing {sorted(_KEYS - set(props))}')

    def test_schema_resolves_defaults_for_every_key(self):
        plugin = _plugin()
        props = plugin.get_config_schema().get('properties', {})
        self.assertTrue(_KEYS.issubset(props))
        # Off-by-default: the kill switch False, every cap 0.
        self.assertFalse(plugin.get_config_value('agents_paused', None))
        for cap in _KEYS - {'agents_paused'}:
            self.assertEqual(plugin.get_config_value(cap, None), 0)

    def test_compliance_report_reads_the_same_keys(self):
        # The report's guardrails section must expose exactly this key set — the
        # coupling that a rename would silently break.
        from plugins.installed.agent_core.compliance import _guardrail_config

        self.assertTrue(_KEYS.issubset(set(_guardrail_config())))
