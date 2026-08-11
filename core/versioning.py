"""Component version inventory — the read-only foundation of the plugin /
theme / core updating system.

Enumerates the running platform's versions: core (``MORPHEUS_VERSION``),
every registered plugin (``Plugin.version`` + enabled state), and every
discovered theme (``MorpheusTheme.version`` + active state). This is the
"what's installed and at what version" layer; remote update-checks and the
apply/rollback orchestration build on top of it (see
``docs/plans/updating-system-2026-06.md``).

Foundational → lives in ``core``: a version inventory that must include core
itself cannot be a disableable plugin (same reasoning as observability and
the self-improvement loop in CLAUDE.md). Pure + fail-soft: never raises, so
it's safe to call from a dashboard, a healthcheck, or a management command.
"""

# ruff: noqa: PLC0415
# Inline imports keep this importable before the app registry is ready.

from __future__ import annotations


def core_version() -> str:
    from django.conf import settings

    return str(getattr(settings, 'MORPHEUS_VERSION', '') or 'unknown')


def plugin_versions() -> list[dict]:
    """``[{name, label, version, enabled}]`` for every registered plugin."""
    try:
        from plugins.registry import app_registry

        active = getattr(app_registry, '_active', set()) or set()
        classes = getattr(app_registry, '_classes', {}) or {}
        return [
            {
                'name': name,
                'label': str(getattr(cls, 'label', name) or name),
                'version': str(getattr(cls, 'version', '') or '0.0.0'),
                'enabled': name in active,
            }
            for name, cls in sorted(classes.items())
        ]
    except Exception:  # noqa: BLE001 — inventory must never break a caller
        return []


def theme_versions() -> list[dict]:
    """``[{name, label, version, active}]`` for every discovered theme."""
    try:
        from themes.registry import theme_registry

        active = theme_registry.active()
        active_name = getattr(active, 'name', None) if active else None
        return [
            {
                'name': getattr(t, 'name', ''),
                'label': str(getattr(t, 'label', getattr(t, 'name', '')) or ''),
                'version': str(getattr(t, 'version', '') or '0.0.0'),
                'active': getattr(t, 'name', None) == active_name,
            }
            for t in theme_registry.all_themes()
        ]
    except Exception:  # noqa: BLE001
        return []


def component_versions() -> dict:
    """Full inventory: ``{core, plugins: [...], themes: [...]}``."""
    return {
        'core': core_version(),
        'plugins': plugin_versions(),
        'themes': theme_versions(),
    }
