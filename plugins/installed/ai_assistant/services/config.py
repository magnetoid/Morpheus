"""Single source of truth for AI provider configuration.

Both the on-store assistant (`plugins/installed/ai_assistant/services/llm.py`)
and the agent runtime (`core/agents/llm.py`) resolve their api keys, base
URLs, and model names through `get_provider_config()`.

Resolution order, highest first:
1. Per-provider value saved in the AI Providers settings panel (dashboard).
2. Legacy generic `settings.AI_MODEL` for the active provider's model only.
3. Provider-specific environment variable (e.g. ``OPENAI_API_KEY``).
4. Hard-coded default (e.g. base URL).

Never raises — returns a `ProviderConfig` with empty strings instead so the
caller can decide how to fail (e.g. fall back to MockLLMProvider).
"""

# Lazy plugin-registry import + fail-soft lookups are intentional. Pre-existing.
# ruff: noqa: PLC0415, S112

from __future__ import annotations

from django.conf import settings

# Canonical type lives in core (plugin→core is the allowed direction); this
# resolver is registered into core's provider_config_registry at ready().
from core.agents.provider_registry import ProviderConfig  # noqa: I001

_DEFAULT_BASE_URLS = {
    'openai': 'https://api.openai.com/v1',
    'anthropic': 'https://api.anthropic.com/v1',
    'gemini': 'https://generativelanguage.googleapis.com/v1beta',
    'openrouter': 'https://openrouter.ai/api/v1',
    'ollama': 'http://localhost:11434',
    'grok': 'https://api.x.ai/v1',
    # apikey.fun — unified gateway, OpenAI-compatible chat-completions endpoint.
    'apikey': 'https://api.apikey.fun/v1',
    # Packy — unified LLM gateway. Wired via its ANTHROPIC-compatible Messages
    # API (serves Claude models); the SDK appends /v1/messages to this root.
    'packy': 'https://www.packyapi.com',
    # Hermes (NousResearch) — defaults to the OpenRouter gateway that hosts the
    # Hermes family; override to Nous's own inference API in the panel.
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


def _plugin():
    """Return the ai_assistant plugin instance, or None if it isn't loaded.

    The registry historically exposed both ``get`` and ``get_plugin`` —
    different builds in flight have only one. Try both before giving up.
    """
    try:
        from plugins.registry import plugin_registry
    except Exception:  # noqa: BLE001
        return None
    for attr in ('get', 'get_plugin'):
        fn = getattr(plugin_registry, attr, None)
        if callable(fn):
            try:
                p = fn('ai_assistant')
            except Exception:  # noqa: BLE001
                continue
            if p is not None:
                return p
    return None


def _cfg(plugin, key: str) -> str:
    if plugin is None:
        return ''
    try:
        v = plugin.get_config_value(key)
    except Exception:  # noqa: BLE001
        return ''
    return (v or '').strip() if isinstance(v, str) else (v or '')


def get_active_provider_name() -> str:
    """Return the active provider chosen in the dashboard (or env fallback)."""
    plugin = _plugin()
    chosen = _cfg(plugin, 'ai_provider') or getattr(settings, 'AI_PROVIDER', '') or 'openai'
    return chosen.strip().lower()


def get_provider_config(provider: str | None = None) -> ProviderConfig:
    """Resolve config for a specific provider (or the active one)."""
    plugin = _plugin()
    name = (provider or get_active_provider_name()).strip().lower()

    api_key = _cfg(plugin, f'{name}_api_key')
    base_url = _cfg(plugin, f'{name}_base_url')
    model = _cfg(plugin, f'{name}_model')

    if not api_key:
        env_keys = {
            'openai': 'OPENAI_API_KEY',
            'anthropic': 'ANTHROPIC_API_KEY',
            'gemini': 'GEMINI_API_KEY',
            'openrouter': 'OPENROUTER_API_KEY',
            'ollama': 'OLLAMA_API_KEY',
            'grok': 'XAI_API_KEY',
            'apikey': 'APIKEY_FUN_API_KEY',
            'packy': 'PACKY_API_KEY',
        }
        api_key = getattr(settings, env_keys.get(name, ''), '') or ''

    if not base_url:
        env_base = {
            'ollama': 'OLLAMA_BASE_URL',
            'openai': 'OPENAI_BASE_URL',
            'openrouter': 'OPENROUTER_BASE_URL',
            'grok': 'XAI_BASE_URL',
            'apikey': 'APIKEY_FUN_BASE_URL',
            'packy': 'PACKY_BASE_URL',
        }
        base_url = getattr(settings, env_base.get(name, ''), '') or _DEFAULT_BASE_URLS.get(name, '')

    if not model:
        # Last-resort: legacy generic AI_MODEL only when it makes sense for
        # this provider (i.e. it's the active one). Otherwise per-provider default.
        if name == get_active_provider_name():
            model = getattr(settings, 'AI_MODEL', '') or _DEFAULT_MODELS.get(name, '')
        else:
            model = _DEFAULT_MODELS.get(name, '')

    embedding_model = (
        _cfg(plugin, f'{name}_embedding_model')
        or getattr(settings, 'AI_EMBEDDING_MODEL', '')
        or 'text-embedding-3-small'
    )

    return ProviderConfig(
        provider=name,
        api_key=api_key,
        base_url=base_url,
        model=model,
        embedding_model=embedding_model,
    )
