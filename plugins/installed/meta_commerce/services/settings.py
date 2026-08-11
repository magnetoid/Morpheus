"""Resolved Meta Commerce configuration (PluginConfig + defaults)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetaSettings:
    enabled: bool
    country: str
    default_brand: str
    default_condition: str
    include_out_of_stock: bool
    feed_title: str
    pixel_enabled: bool


# NOTE: there is intentionally no `currency` override — Meta requires the feed
# currency to match the actual price currency, and we don't convert, so a
# label-only override would emit misleading prices. Each item carries the
# product's own currency (see mapping._money).
_DEFAULTS = {
    'enabled': True,
    'country': 'US',
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
        from plugins.registry import app_registry  # noqa: PLC0415

        for attr in ('get', 'get_plugin'):
            fn = getattr(app_registry, attr, None)
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
