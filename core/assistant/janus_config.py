"""Resolve Janus engine config: dashboard overlay, then Django/env.

Linda is brand. This module is the single read path so ``janus_engine`` and
the settings view cannot drift. Tests pin ``LINDA_ENGINE='legacy'`` in
``morph/settings.py``; a process-level ``legacy`` pin always wins so a leftover
DB row cannot spawn a real engine in the suite.
"""

from __future__ import annotations

import os
from typing import Any

_DEFAULT_TIMEOUT_S = 55


def _django_settings():
    try:
        from django.conf import settings

        return settings
    except Exception:  # noqa: BLE001
        return None


def _row():
    try:
        from core.assistant.models import JanusSettings

        return JanusSettings.load()
    except Exception:  # noqa: BLE001 — migrations / app registry
        return None


def resolved_engine() -> str:
    s = _django_settings()
    django_engine = str(getattr(s, 'LINDA_ENGINE', 'janus') or 'janus').lower() if s else 'janus'
    if django_engine == 'legacy':
        return 'legacy'
    row = _row()
    if row is not None and (row.engine or '') in ('janus', 'legacy'):
        return row.engine
    return django_engine if django_engine in ('janus', 'legacy') else 'janus'


def resolved_auto_approve() -> bool:
    s = _django_settings()
    django_val = bool(getattr(s, 'LINDA_JANUS_AUTO_APPROVE', False) if s else False)
    row = _row()
    if row is None or not row.pk:
        return django_val
    return bool(row.auto_approve)


def resolved_timeout_s() -> int:
    s = _django_settings()
    raw = getattr(s, 'LINDA_JANUS_TIMEOUT_S', _DEFAULT_TIMEOUT_S) if s else _DEFAULT_TIMEOUT_S
    try:
        django_val = max(5, int(raw))
    except (TypeError, ValueError):
        django_val = _DEFAULT_TIMEOUT_S
    row = _row()
    if row is not None and row.timeout_s:
        return max(5, min(55, int(row.timeout_s)))
    return min(django_val, 55)


def resolved_model() -> str:
    row = _row()
    if row is not None and (row.model or '').strip():
        return row.model.strip()
    return os.environ.get('JANUS_INFERENCE_MODEL') or 'auto'


def resolved_mcp_url() -> str:
    row = _row()
    if row is not None and (row.mcp_url or '').strip():
        return row.mcp_url.strip().rstrip('/') + '/'
    s = _django_settings()
    explicit = (getattr(s, 'LINDA_MCP_URL', '') if s else '') or os.environ.get('LINDA_MCP_URL', '')
    if explicit:
        return explicit.rstrip('/') + '/'
    return ''


def resolved_mcp_token() -> str:
    row = _row()
    if row is not None and (row.mcp_token or '').strip():
        return row.mcp_token.strip()
    s = _django_settings()
    return (getattr(s, 'LINDA_MCP_TOKEN', '') if s else '') or os.environ.get('LINDA_MCP_TOKEN', '')


def status_snapshot() -> dict[str, Any]:
    """Read-only status for the Linda settings page."""
    from core.assistant.janus_engine import bundled_skill_names, janus_available

    engine = resolved_engine()
    available = janus_available()
    return {
        'engine': engine,
        'binary_ok': available,
        'live': engine == 'janus' and available,
        'model': resolved_model(),
        'timeout_s': resolved_timeout_s(),
        'auto_approve': resolved_auto_approve(),
        'mcp_configured': bool(resolved_mcp_url() and resolved_mcp_token()),
        'skills': bundled_skill_names(),
    }
