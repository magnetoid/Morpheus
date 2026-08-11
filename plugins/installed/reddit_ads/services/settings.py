"""Reddit Ads configuration (PluginConfig)."""

from __future__ import annotations


def _plugin():
    try:
        from plugins.registry import app_registry  # noqa: PLC0415

        for attr in ('get', 'get_plugin'):
            fn = getattr(app_registry, attr, None)
            if callable(fn):
                try:
                    p = fn('reddit_ads')
                except Exception:  # noqa: BLE001
                    p = None
                if p is not None:
                    return p
    except Exception:  # noqa: BLE001
        return None
    return None


def raw_config() -> dict:
    p = _plugin()
    if p is None:
        return {}
    try:
        return p.get_config() or {}
    except Exception:  # noqa: BLE001
        return {}


def pixel_enabled() -> bool:
    return bool(raw_config().get('pixel_enabled'))
