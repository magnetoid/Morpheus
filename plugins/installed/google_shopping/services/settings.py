"""Resolved Google Shopping configuration.

Reads PluginConfig (set in the dashboard settings panel) with sane defaults, so
every service shares one view of the merchant's feed config and the field
defaults never drift from the JSON schema.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedSettings:
    enabled: bool
    merchant_id: str
    country: str
    language: str
    currency: str
    default_brand: str
    default_google_product_category: str
    default_condition: str
    free_shipping_over: str
    include_out_of_stock: bool
    feed_title: str
    feed_description: str


_DEFAULTS = {
    'enabled': True,
    'merchant_id': '',
    'country': 'US',
    'language': 'en',
    'currency': '',  # '' → fall back to the product's own currency
    'default_brand': '',
    'default_google_product_category': '',
    'default_condition': 'new',
    'free_shipping_over': '',
    'include_out_of_stock': True,
    'feed_title': 'Dot Books',
    'feed_description': 'Product feed for Google Merchant Center.',
}


def feed_settings() -> FeedSettings:
    cfg = dict(_DEFAULTS)
    try:
        from plugins.registry import plugin_registry  # noqa: PLC0415

        plugin = None
        for attr in ('get', 'get_plugin'):
            fn = getattr(plugin_registry, attr, None)
            if callable(fn):
                try:
                    plugin = fn('google_shopping')
                except Exception:  # noqa: BLE001
                    plugin = None
                if plugin is not None:
                    break
        if plugin is not None:
            stored = plugin.get_config() or {}
            cfg.update({k: v for k, v in stored.items() if k in _DEFAULTS})
    except Exception:  # noqa: BLE001, S110 — defaults are always safe
        pass
    return FeedSettings(**cfg)
