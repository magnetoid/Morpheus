"""Which provider and model a Janus turn is pinned to, and its backups.

A leaf of :mod:`core.assistant.janus_engine`, which re-exports every name here.
The functions in this file read each other here: a test that replaces one of them
for another patches this module, not the engine.
"""

from __future__ import annotations

import logging

from core.assistant import janus_settings

logger = logging.getLogger('morpheus.assistant.janus')


# Morpheus provider name → (Janus ``--provider`` id, API-key env var, base-URL env
# var), from janus_cli/auth.py's ProviderConfig table. Janus's ``auto`` routes to
# OpenRouter whenever OPENAI_API_KEY is set, and it never sees a key that lives
# in the dashboard rather than the environment. Production had both at once: the
# active provider was DeepSeek with its key in the dashboard, so every turn went
# to the wrong provider with the wrong key.
_JANUS_PROVIDERS = {
    'openai': ('openai-api', 'OPENAI_API_KEY', 'OPENAI_BASE_URL'),
    'anthropic': ('anthropic', 'ANTHROPIC_API_KEY', 'ANTHROPIC_BASE_URL'),
    'gemini': ('gemini', 'GEMINI_API_KEY', 'GEMINI_BASE_URL'),
    'deepseek': ('deepseek', 'DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL'),
    'grok': ('xai', 'XAI_API_KEY', 'XAI_BASE_URL'),
    'qwen': ('alibaba', 'DASHSCOPE_API_KEY', 'DASHSCOPE_BASE_URL'),
}


def pinnable_providers() -> tuple[str, ...]:
    """Morpheus provider names Janus can be pinned to (Settings → AI → Janus)."""
    return tuple(_JANUS_PROVIDERS)


_PROVIDER_LABELS = {
    'openai': 'OpenAI',
    'anthropic': 'Anthropic',
    'gemini': 'Gemini',
    'deepseek': 'DeepSeek',
    'grok': 'Grok',
    'qwen': 'Qwen Cloud',
}


def _configured(name: str):
    """(Janus spec, provider config) for a provider Janus can run that has a key."""
    spec = _JANUS_PROVIDERS.get(name)
    if spec is None:
        return None
    try:
        from core.agents.provider_registry import get_provider_config

        cfg = get_provider_config(name)
    except Exception:  # noqa: BLE001 — an unreadable provider is simply not offered
        return None
    return (spec, cfg) if cfg.api_key and cfg.model else None


def selectable_providers() -> list[dict[str, str]]:
    """Providers a message can be sent to: Janus runs them, they have a key, and
    their model is priced — an unpriced model would escape the daily spend cap."""
    from core.agents.pricing import is_priced

    out = []
    for name in _JANUS_PROVIDERS:
        found = _configured(name)
        if found is None or not is_priced(found[1].model):
            continue
        model = found[1].model
        out.append(
            {'name': name, 'model': model, 'label': f'{_PROVIDER_LABELS.get(name, name)} · {model}'}
        )
    return out


def _fallback_wiring(primary_env: dict[str, str]) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Backup providers for `fallback_providers` (Settings → AI → Janus) and their keys.

    Janus switches to the next one when the main provider fails a call (quota,
    rate limit, overload). Keys stored in the dashboard never reach Janus's own
    environment, so each backup's key travels with the turn like the main one.
    The main provider is never its own backup.
    """
    from core.agents.pricing import is_priced

    entries: list[dict[str, str]] = []
    env: dict[str, str] = {}
    for name in janus_settings.fallback_providers():
        found = _configured(name)
        if found is None:
            continue
        (janus_id, key_var, base_var), cfg = found
        if key_var in primary_env or key_var in env or not is_priced(cfg.model):
            continue
        entries.append({'provider': janus_id, 'model': cfg.model})
        env[key_var] = cfg.api_key
        if cfg.base_url:
            env[base_var] = cfg.base_url
    return entries, env


class UnsupportedProvider(Exception):
    """The store's AI provider is one Janus has no name for. ``str()`` is the provider."""


def _provider_wiring(choice: str = '') -> tuple[list[str], dict[str, str]]:
    """CLI args + env that pin Janus to its provider.

    The provider picked for this message in the composer (when it is one of
    :func:`selectable_providers`), else the one pinned on Settings → AI → Janus,
    else the store's active AI provider. Raises :class:`UnsupportedProvider` when
    that one is not in ``_JANUS_PROVIDERS``.
    """
    custom = janus_settings.custom_provider()
    picked = (
        _configured(choice)
        if choice and choice in {p['name'] for p in selectable_providers()}
        else None
    )
    if picked is not None:
        name, model, api_key, base_url = (
            choice,
            picked[1].model,
            picked[1].api_key,
            picked[1].base_url,
        )
    elif custom is not None:
        name, model, api_key, base_url = (
            custom['provider'],
            custom['model'],
            custom['api_key'],
            custom['base_url'],
        )
    else:
        try:
            from core.agents.provider_registry import get_active_provider_name, get_provider_config

            name = get_active_provider_name()
            cfg = get_provider_config(name)
        except Exception:  # noqa: BLE001 — fall back to Janus's own resolution
            logger.warning(
                'janus: provider config unavailable; Janus will auto-select', exc_info=True
            )
            return [], {}
        model, api_key, base_url = cfg.model, cfg.api_key, cfg.base_url
    spec = _JANUS_PROVIDERS.get(name)
    if spec is None:
        # Never left to Janus's own `auto`: it picks a model from whatever keys the
        # container holds, one the store did not choose and may not have priced.
        raise UnsupportedProvider(name)
    if not api_key:
        logger.warning('janus: no key for provider %r; Janus will auto-select', name)
        return [], {}
    janus_id, key_var, base_var = spec
    args = ['--provider', janus_id]
    if model:
        args += ['-m', model]
    env = {key_var: api_key}
    if base_url:
        env[base_var] = base_url
    return args, env
