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
    remarketing_enabled: bool
    remarketing_id: str


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
    'remarketing_enabled': False,
    'remarketing_id': '',
}


def _plugin():
    """The registry's live google_shopping plugin instance (or None)."""
    try:
        from plugins.registry import app_registry  # noqa: PLC0415

        for attr in ('get', 'get_plugin'):
            fn = getattr(app_registry, attr, None)
            if callable(fn):
                try:
                    p = fn('google_shopping')
                except Exception:  # noqa: BLE001
                    p = None
                if p is not None:
                    return p
    except Exception:  # noqa: BLE001
        return None
    return None


def raw_config() -> dict:
    """The full PluginConfig dict — used for OAuth/API secrets that don't belong
    in the FeedSettings dataclass."""
    p = _plugin()
    if p is None:
        return {}
    try:
        return p.get_config() or {}
    except Exception:  # noqa: BLE001
        return {}


def feed_settings() -> FeedSettings:
    cfg = dict(_DEFAULTS)
    stored = raw_config()
    cfg.update({k: v for k, v in stored.items() if k in _DEFAULTS})
    return FeedSettings(**cfg)
