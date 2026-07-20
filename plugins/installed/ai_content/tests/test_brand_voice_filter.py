"""Brand voice rides the AGENT_SYSTEM_PROMPT filter (boundary refactor, Phase 3).

core/agents/base.py and core/assistant/prompts.py no longer import
ai_content.services — they fire ``AGENT_SYSTEM_PROMPT`` and this plugin's
subscriber prepends the brand voice. Disable-safety comes from the bus
(inactive owners are skipped), replacing the old ``try/except → ''``.
"""

from __future__ import annotations

from django.test import TestCase

from plugins.registry import plugin_registry


def _set_brand(name: str) -> None:
    plugin = plugin_registry.get('ai_content')
    plugin.set_config('brand_name', name)


class BrandVoiceFilterTests(TestCase):
    def test_linda_prompt_carries_brand_voice_when_configured(self):
        from core.assistant.prompts import build_system_prompt

        _set_brand('Dot Books')
        prompt = build_system_prompt()
        self.assertTrue(prompt.startswith('BRAND VOICE'), prompt[:60])
        self.assertIn('Dot Books', prompt)

    def test_agent_prompt_carries_brand_voice_when_configured(self):
        from core.agents import agent_registry

        _set_brand('Dot Books')
        worker = agent_registry.get_agent('worker')
        prompt = worker.get_system_prompt()
        self.assertTrue(prompt.startswith('BRAND VOICE'), prompt[:60])

    def test_blanked_config_yields_plain_prompt(self):
        from core.assistant.prompts import LINDA_BASE_PROMPT, build_system_prompt

        # All four fields blank → get_brand_voice() is '' → prompt verbatim.
        # (NB `brand_tone` has a non-empty schema DEFAULT, so a fresh store
        # DOES carry a voice fragment — same as the old direct-import path.)
        plugin = plugin_registry.get('ai_content')
        for key in ('brand_name', 'brand_audience', 'brand_tone', 'brand_voice_guidelines'):
            plugin.set_config(key, '')
        self.assertEqual(build_system_prompt(), LINDA_BASE_PROMPT)

    def test_disabled_plugin_yields_plain_prompt(self):
        from core.assistant.prompts import LINDA_BASE_PROMPT, build_system_prompt

        _set_brand('Dot Books')
        self.assertIn('BRAND VOICE', build_system_prompt())  # sanity: active first
        plugin_registry.deactivate('ai_content')
        try:
            # Bus skips the inactive owner's handler → plain prompt, no error.
            self.assertEqual(build_system_prompt(), LINDA_BASE_PROMPT)
        finally:
            plugin_registry.activate('ai_content')
        self.assertIn('BRAND VOICE', build_system_prompt())  # restored on re-enable
