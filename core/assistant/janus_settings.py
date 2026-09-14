"""Merchant settings for Linda's engine (Janus), read cross-process fresh.

The merchant edits these on Settings → AI → Janus (the ``janus`` app). The engine
and the turn runtime read them here, through the app registry, so core never
imports the app — the same inversion ``core/agents/guardrails.py`` uses. Each
read invalidates the app's per-process config cache first: a Celery worker or a
second gunicorn worker would otherwise keep serving a value the merchant already
changed in another process.

Everything fails soft to the built-in default. A broken settings read must never
switch Linda off, and must never widen anything: the one widening input, a
custom provider, only applies when its provider, model and key are all valid.
"""

from __future__ import annotations

from typing import Any

APP = 'janus'

#: Hard bounds. The timeout cap is load-bearing: the turn blocks a gunicorn
#: worker whose own timeout is 60s (scripts/docker-entrypoint.sh).
MAX_TURN_TIMEOUT_S = 55
MIN_TURN_TIMEOUT_S = 10
MAX_TOOL_TURNS = 10
MAX_EXTRA_INSTRUCTIONS = 4000


def _read(key: str, default: Any) -> Any:
    try:
        from plugins.registry import app_registry

        app = app_registry.get(APP)
        if app is None:
            return default
        app.invalidate_config_cache()
        value = app.get_config_value(key, default)
        return default if value is None else value
    except Exception:  # noqa: BLE001 — settings trouble must not wedge Linda
        return default


def _int(key: str, default: int, low: int, high: int) -> int:
    try:
        return min(high, max(low, int(_read(key, default))))
    except (TypeError, ValueError):
        return default


def engine_enabled() -> bool:
    return bool(_read('enabled', True))


def max_tool_turns(default: int) -> int:
    return _int('max_tool_turns', default, 1, MAX_TOOL_TURNS)


def turn_timeout_s(default: int) -> int:
    return _int('turn_timeout_s', default, MIN_TURN_TIMEOUT_S, MAX_TURN_TIMEOUT_S)


def extra_instructions() -> str:
    return str(_read('extra_instructions', '') or '').strip()[:MAX_EXTRA_INSTRUCTIONS]


def bundled_skills_enabled() -> bool:
    return bool(_read('bundled_skills', True))


def custom_provider() -> dict[str, str] | None:
    """The merchant's pinned provider for Janus, or None to use the store's AI provider."""
    if _read('model_source', 'store') != 'custom':
        return None
    provider = str(_read('provider', '') or '')
    model = str(_read('model', '') or '').strip()
    api_key = str(_read('api_key', '') or '').strip()
    from core.assistant.janus_engine import pinnable_providers

    if provider not in pinnable_providers() or not model or not api_key:
        return None
    return {
        'provider': provider,
        'model': model,
        'api_key': api_key,
        'base_url': str(_read('base_url', '') or '').strip(),
    }
