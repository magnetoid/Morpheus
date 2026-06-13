"""Provider-config registry decouples core from the ai_assistant plugin.

Core resolves LLM provider config through this registry, falling back to an
env/settings-only default when no plugin has registered a richer resolver — so
the kernel never imports plugins.installed.ai_assistant.
"""

from __future__ import annotations

from django.test import SimpleTestCase, override_settings

from core.agents.provider_registry import (
    ProviderConfig,
    get_active_provider_name,
    get_provider_config,
    provider_config_registry,
)


class ProviderRegistryTests(SimpleTestCase):
    def setUp(self):
        # The ai_assistant plugin registers its resolver at ready(); snapshot
        # and restore so these tests can exercise the bare default in isolation.
        self._saved = (
            provider_config_registry._config_resolver,
            provider_config_registry._active_resolver,
        )
        provider_config_registry.reset()

    def tearDown(self):
        provider_config_registry._config_resolver = self._saved[0]
        provider_config_registry._active_resolver = self._saved[1]

    @override_settings(AI_PROVIDER='anthropic')
    def test_default_active_provider_from_settings(self):
        self.assertEqual(get_active_provider_name(), 'anthropic')

    @override_settings(AI_PROVIDER='openai', OPENAI_API_KEY='sk-env-xyz')
    def test_default_resolver_uses_env_without_plugin(self):
        cfg = get_provider_config('openai')
        self.assertIsInstance(cfg, ProviderConfig)
        self.assertEqual(cfg.provider, 'openai')
        self.assertEqual(cfg.api_key, 'sk-env-xyz')
        # Falls back to the baked-in default base URL + model.
        self.assertEqual(cfg.base_url, 'https://api.openai.com/v1')
        self.assertEqual(cfg.model, 'gpt-4o-mini')

    def test_unknown_provider_is_safe(self):
        cfg = get_provider_config('does-not-exist')
        self.assertEqual(cfg.api_key, '')  # never raises

    def test_registered_resolver_overrides_default(self):
        sentinel = ProviderConfig(
            provider='openai',
            api_key='dash-key',
            base_url='https://dash',
            model='dash-model',
            embedding_model='e',
        )
        provider_config_registry.register(lambda name: sentinel, lambda: 'grok')
        self.assertIs(get_provider_config('openai'), sentinel)
        self.assertEqual(get_active_provider_name(), 'grok')

    @override_settings(AI_PROVIDER='openai')
    def test_failing_resolver_falls_back_to_default(self):
        def boom(_name):
            raise RuntimeError('resolver down')

        provider_config_registry.register(boom)
        # Must not raise — degrades to env/default resolution.
        cfg = get_provider_config('openai')
        self.assertEqual(cfg.provider, 'openai')
        self.assertEqual(cfg.model, 'gpt-4o-mini')
