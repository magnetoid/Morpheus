"""This store's actual return policy, as structured data.

The SEO app used to publish a complete `MerchantReturnPolicy` — 30 days, free
returns, by mail, US — on every product page of every store, assembled from
constants in its own source. Only the window was ever real. This app owns the
return window, so it states the window; it says nothing about fees or methods,
because it does not know them and a guess about who pays for a return is the
kind of guess that ends in a chargeback.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.returns_portal')

# Mirrors the schema default in app.py:get_config_schema.
_DEFAULT_WINDOW_DAYS = 30


def on_seo_jsonld_graph(value, page=None, request=None, **kwargs):
    """`SEO_JSONLD_GRAPH` subscriber: add the return policy to the offer."""
    try:
        offer = _product_offer(value)
        if offer is None:
            return value
        policy = return_policy()
        if policy:
            offer['hasMerchantReturnPolicy'] = policy
    except Exception as e:  # noqa: BLE001 — never lose the graph over an enricher
        logger.warning('returns_portal: JSON-LD enrichment failed: %s', e, exc_info=True)
    return value


def return_policy() -> dict | None:
    """`MerchantReturnPolicy` from the merchant's configured window.

    Returns None when the country is unknown: `applicableCountry` is required,
    and a policy that names the wrong country is worse than no policy at all.
    """
    from plugins.registry import app_registry

    plugin = app_registry.get('returns_portal')
    config = (plugin.get_config() if plugin else {}) or {}
    # `get_config` returns what was SAVED, not the schema defaults, so an
    # untouched store has an empty dict — and its policy is still the documented
    # 30 days, which is what the returns portal itself honours. An explicit 0 is
    # a different statement ("no returns") and is preserved.
    try:
        days = int(
            _DEFAULT_WINDOW_DAYS
            if 'return_window_days' not in config
            else (config.get('return_window_days') or 0)
        )
    except (TypeError, ValueError):
        days = _DEFAULT_WINDOW_DAYS

    country = _store_country()
    if not country:
        return None

    if days <= 0:
        # A store that takes no returns should say so plainly rather than go
        # silent — "no returns" is a legitimate, and disclosable, policy.
        return {
            '@type': 'MerchantReturnPolicy',
            'applicableCountry': country,
            'returnPolicyCategory': 'https://schema.org/MerchantReturnNotPermitted',
        }
    return {
        '@type': 'MerchantReturnPolicy',
        'applicableCountry': country,
        'returnPolicyCategory': 'https://schema.org/MerchantReturnFiniteReturnWindow',
        'merchantReturnDays': days,
    }


def _store_country() -> str:
    """The merchant's own country, from Settings → General."""
    try:
        from core.models import StoreSettings

        store = StoreSettings.objects.first()
        return (getattr(store, 'country', '') or '').strip().upper()[:2]
    except Exception:  # noqa: BLE001 — unmigrated DB during a deploy
        return ''


def _product_offer(graph) -> dict | None:
    if not isinstance(graph, dict):
        return None
    for node in graph.get('@graph') or []:
        if not isinstance(node, dict) or 'Product' not in str(node.get('@type', '')):
            continue
        offer = node.get('offers')
        if isinstance(offer, dict):
            return offer
    return None
