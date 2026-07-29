"""gdpr customises the Art. 50 AI-disclosure wording — disable-safe.

gdpr subscribes to AI_SURFACE_DISCLOSURE to let a merchant replace the core
default wording. When gdpr is disabled, the shared bus skips its handler and the
caller keeps the core legal-floor default — the disclosure never disappears.
"""

from __future__ import annotations

from django.test import TestCase

from morpheus.core import MorpheusEvents, hook_registry
from plugins.registry import plugin_registry

_CORE_DEFAULT = 'CORE-DEFAULT-SENTINEL'


def _disclosure(value: str = _CORE_DEFAULT) -> str:
    return hook_registry.filter(
        MorpheusEvents.AI_SURFACE_DISCLOSURE, value=value, surface='ai_stylist'
    )


class GdprAiDisclosureTests(TestCase):
    def setUp(self):
        self._plugin = plugin_registry.get('gdpr')
        self.assertIsNotNone(self._plugin, 'gdpr plugin must be registered')
        self.addCleanup(plugin_registry.activate, 'gdpr')
        self.addCleanup(self._plugin.invalidate_config_cache)

    def test_blank_config_falls_back_to_core_default(self):
        self._plugin.invalidate_config_cache()
        plugin_registry.activate('gdpr')
        self.assertEqual(_disclosure(), _CORE_DEFAULT)

    def test_merchant_override_replaces_wording(self):
        plugin_registry.activate('gdpr')
        self._plugin.set_config('ai_disclosure_text', 'Meet Aria, our AI helper.')
        self.addCleanup(self._plugin.set_config, 'ai_disclosure_text', '')
        self.assertEqual(_disclosure(), 'Meet Aria, our AI helper.')

    def test_disable_safety_gdpr_off_yields_core_default(self):
        self._plugin.set_config('ai_disclosure_text', 'Custom AI note.')
        self.addCleanup(self._plugin.set_config, 'ai_disclosure_text', '')
        plugin_registry.activate('gdpr')
        self.assertEqual(_disclosure(), 'Custom AI note.')
        # Toggle gdpr off → its handler is skipped → the core default survives.
        plugin_registry.deactivate('gdpr')
        self.assertEqual(_disclosure(), _CORE_DEFAULT)
        # Re-enable → merchant wording returns.
        plugin_registry.activate('gdpr')
        self.assertEqual(_disclosure(), 'Custom AI note.')
