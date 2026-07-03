"""Every provider offered in the dashboard catalog must have a probe, so its
'Test' / 'Fetch models' buttons work. DeepSeek/apikey/hermes shipped without
one and silently returned 'unknown provider' — this guards against the drift.
"""

from __future__ import annotations

from django.test import SimpleTestCase


class ProbeCoverageTests(SimpleTestCase):
    def test_every_catalog_provider_has_a_probe(self):
        from plugins.installed.admin_dashboard.views_split.settings import _AI_PROVIDERS
        from plugins.installed.ai_assistant.services.probe import _PROBES

        catalog = {p['slug'] for p in _AI_PROVIDERS}
        missing = catalog - set(_PROBES)
        self.assertEqual(missing, set(), f'catalog providers with no probe: {missing}')

    def test_deepseek_probe_registered(self):
        from plugins.installed.ai_assistant.services.probe import _PROBES, probe_deepseek

        self.assertIs(_PROBES.get('deepseek'), probe_deepseek)

    def test_probe_without_key_fails_cleanly(self):
        from plugins.installed.ai_assistant.services.probe import probe

        out = probe('deepseek', api_key='', base_url='')
        self.assertFalse(out['ok'])
        self.assertIn('API key', out['error'])

    def test_unknown_provider_still_reported(self):
        from plugins.installed.ai_assistant.services.probe import probe

        out = probe('does-not-exist')
        self.assertFalse(out['ok'])
        self.assertIn('unknown provider', out['error'])
