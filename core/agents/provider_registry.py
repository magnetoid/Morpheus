"""Provider-config registry — the kernel's source of truth for LLM provider
settings, decoupled from any plugin.

`core/agents/llm.py` and `core/assistant/consensus.py` resolve api keys, base
URLs, and model names through :func:`get_provider_config` /
:func:`get_active_provider_name`. By **default** these read only environment
variables / Django settings, so the agent kernel boots and runs even when the
``ai_assistant`` plugin is absent or disabled.

The ``ai_assistant`` plugin *enriches* resolution with dashboard-saved settings
by calling ``provider_config_registry.register(...)`` in its ``ready()``. That
keeps the dependency pointing the allowed direction — the plugin reaches into
core, never the reverse. (Before this registry, core imported
``plugins.installed.ai_assistant.services.config`` directly, a forbidden
core→plugin edge.)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger('morpheus.agents')


@dataclass(slots=True)
class ProviderConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    embedding_model: str


# Sensible defaults so a provider works with only an API key set. Mirrored by
# the ai_assistant plugin's richer resolver; kept here so core stands alone.
_DEFAULT_BASE_URLS = {
    'openai': 'https://api.openai.com/v1',
    'anthropic': 'https://api.anthropic.com/v1',
    'gemini': 'https://generativelanguage.googleapis.com/v1beta',
    'openrouter': 'https://openrouter.ai/api/v1',
    'ollama': 'http://localhost:11434',
    'grok': 'https://api.x.ai/v1',
    'apikey': 'https://api.apikey.fun/v1',
    'packy': 'https://www.packyapi.com',
    'hermes': 'https://openrouter.ai/api/v1',
}

_DEFAULT_MODELS = {
    'openai': 'gpt-4o-mini',
    'anthropic': 'claude-3-5-sonnet-latest',
    'gemini': 'gemini-2.0-flash',
    'openrouter': 'anthropic/claude-3.5-sonnet',
    'ollama': 'llama3.2',
    'grok': 'grok-4',
    'apikey': 'gpt-4o-mini',
    'packy': 'claude-3-5-sonnet-20241022',
    'hermes': 'nousresearch/hermes-3-llama-3.1-405b',
}

_ENV_KEYS = {
    'openai': 'OPENAI_API_KEY',
    'anthropic': 'ANTHROPIC_API_KEY',
    'gemini': 'GEMINI_API_KEY',
    'openrouter': 'OPENROUTER_API_KEY',
    'ollama': 'OLLAMA_API_KEY',
    'grok': 'XAI_API_KEY',
    'apikey': 'APIKEY_FUN_API_KEY',
    'packy': 'PACKY_API_KEY',
}

_ENV_BASE = {
    'ollama': 'OLLAMA_BASE_URL',
    'openai': 'OPENAI_BASE_URL',
    'openrouter': 'OPENROUTER_BASE_URL',
    'grok': 'XAI_BASE_URL',
    'apikey': 'APIKEY_FUN_BASE_URL',
    'packy': 'PACKY_BASE_URL',
}


def _default_active_provider_name() -> str:
    """Active provider from Django settings only (no plugin/dashboard)."""
    return (getattr(settings, 'AI_PROVIDER', '') or 'openai').strip().lower()


def _default_get_provider_config(provider: str | None = None) -> ProviderConfig:
    """Env/settings-only resolver. Never raises — empty strings when unset."""
    name = (provider or _default_active_provider_name()).strip().lower()

    api_key = getattr(settings, _ENV_KEYS.get(name, ''), '') or ''
    base_url = getattr(settings, _ENV_BASE.get(name, ''), '') or _DEFAULT_BASE_URLS.get(name, '')

    if name == _default_active_provider_name():
        model = getattr(settings, 'AI_MODEL', '') or _DEFAULT_MODELS.get(name, '')
    else:
        model = _DEFAULT_MODELS.get(name, '')

    embedding_model = getattr(settings, 'AI_EMBEDDING_MODEL', '') or 'text-embedding-3-small'

    return ProviderConfig(
        provider=name,
        api_key=api_key,
        base_url=base_url,
        model=model,
        embedding_model=embedding_model,
    )


class _ProviderConfigRegistry:
    """Holds the active resolver. Plugins register a richer one; core falls
    back to the env-only default when nothing is registered (or a resolver
    raises)."""

    def __init__(self) -> None:
        self._config_resolver: Callable[[str | None], ProviderConfig] | None = None
        self._active_resolver: Callable[[], str] | None = None

    def register(
        self,
        config_resolver: Callable[[str | None], ProviderConfig],
        active_resolver: Callable[[], str] | None = None,
    ) -> None:
        """Install a resolver (idempotent — last registration wins)."""
        self._config_resolver = config_resolver
        if active_resolver is not None:
            self._active_resolver = active_resolver

    def reset(self) -> None:
        """Drop any registered resolver (used by tests + on plugin disable)."""
        self._config_resolver = None
        self._active_resolver = None

    def get_provider_config(self, provider: str | None = None) -> ProviderConfig:
        if self._config_resolver is not None:
            try:
                return self._config_resolver(provider)
            except Exception:  # noqa: BLE001 — a bad resolver must not break the kernel
                logger.warning(
                    'provider_registry: resolver failed, using env defaults', exc_info=True
                )
        return _default_get_provider_config(provider)

    def get_active_provider_name(self) -> str:
        if self._active_resolver is not None:
            try:
                return self._active_resolver()
            except Exception:  # noqa: BLE001
                logger.warning(
                    'provider_registry: active resolver failed, using env', exc_info=True
                )
        return _default_active_provider_name()


provider_config_registry = _ProviderConfigRegistry()


def get_provider_config(provider: str | None = None) -> ProviderConfig:
    """Resolve config for a provider (or the active one). Never raises."""
    return provider_config_registry.get_provider_config(provider)


def get_active_provider_name() -> str:
    """The active provider name (dashboard-aware when the plugin is loaded)."""
    return provider_config_registry.get_active_provider_name()
