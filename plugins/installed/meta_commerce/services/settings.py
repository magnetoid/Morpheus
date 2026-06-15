"""Resolved Meta Commerce configuration (PluginConfig + defaults)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetaSettings:
    enabled: bool
    country: str
    currency: str
    default_brand: str
    default_condition: str
    include_out_of_stock: bool
    feed_title: str
    pixel_enabled: bool


_DEFAULTS = {
    'enabled': True,
    'country': 'US',
    'currency': '',  # '' → use the product's own currency
    'default_brand': '',
    'default_condition': 'new',
    'include_out_of_stock': True,
    'feed_title': 'Dot Books',
    'pixel_enabled': False,
}

# Secret/ID fields read via raw_config() (not in the dataclass).
_SECRET_KEYS = ('access_token', 'catalog_id', 'ad_account_id', 'pixel_id', 'business_id')


def _plugin():
    try:
        from plugins.registry import plugin_registry  # noqa: PLC0415

        for attr in ('get', 'get_plugin'):
            fn = getattr(plugin_registry, attr, None)
            if callable(fn):
                try:
                    p = fn('meta_commerce')
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


def meta_settings() -> MetaSettings:
    cfg = dict(_DEFAULTS)
    cfg.update({k: v for k, v in raw_config().items() if k in _DEFAULTS})
    return MetaSettings(**cfg)
