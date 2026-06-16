"""Resolved Microsoft Commerce configuration (PluginConfig + defaults)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MicrosoftSettings:
    enabled: bool
    country: str
    default_brand: str
    default_condition: str
    include_out_of_stock: bool
    feed_title: str
    uet_enabled: bool


_DEFAULTS = {
    'enabled': True,
    'country': 'US',
    'default_brand': '',
    'default_condition': 'new',
    'include_out_of_stock': True,
    'feed_title': 'Dot Books',
    'uet_enabled': False,
}


def _plugin():
    try:
        from plugins.registry import plugin_registry  # noqa: PLC0415

        for attr in ('get', 'get_plugin'):
            fn = getattr(plugin_registry, attr, None)
            if callable(fn):
                try:
                    p = fn('microsoft_commerce')
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


def microsoft_settings() -> MicrosoftSettings:
    cfg = dict(_DEFAULTS)
    cfg.update({k: v for k, v in raw_config().items() if k in _DEFAULTS})
    return MicrosoftSettings(**cfg)
