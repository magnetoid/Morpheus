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
    """`SEO_JSONLD_GRAPH` subscriber: the return policy, on the store and the offer.

    On the store's own node (Google reads an Organization-level policy since
    June 2025) it covers every product the store sells, so a product page whose
    offer Google cannot pair with a policy, and every listing page, still says
    what returns cost the shopper. On the offer it states the same policy
    where Google looks first.

    It is a policy for goods sent to the shopper, so only a product that ships
    gets it, and the store only while it sells one: the travel stores published
    a 30-day return window on every experience and hotel.
    """
    try:
        offers = _product_offers(value) if page_product_ships(page) else []
        store = _store_node(value) if store_ships_goods() else None
        if not offers and store is None:
            return value
        policy = return_policy()
        if policy:
            for offer in offers:
                offer['hasMerchantReturnPolicy'] = dict(policy)
            if store is not None:
                store['hasMerchantReturnPolicy'] = dict(policy)
    except Exception as e:  # noqa: BLE001 — never lose the graph over an enricher
        logger.warning('returns_portal: JSON-LD enrichment failed: %s', e, exc_info=True)
    return value


def return_policy() -> dict | None:
    """`MerchantReturnPolicy` from the merchant's configured window.

    Returns None when the country is unknown: `applicableCountry` is required,
    and a policy that names the wrong country is worse than no policy at all.
    """
    days = window_days()
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


def window_days() -> int:
    """The return window the merchant set, in days (0 = no returns).

    `get_config` returns what was SAVED, not the schema defaults, so an
    untouched store has an empty dict — and its policy is still the documented
    30 days, which is what the returns portal itself honours. An explicit 0 is
    a different statement ("no returns") and is preserved.
    """
    from plugins.registry import app_registry

    plugin = app_registry.get('returns_portal')
    config = (plugin.get_config() if plugin else {}) or {}
    try:
        return max(
            int(
                _DEFAULT_WINDOW_DAYS
                if 'return_window_days' not in config
                else (config.get('return_window_days') or 0)
            ),
            0,
        )
    except (TypeError, ValueError):
        return _DEFAULT_WINDOW_DAYS


def page_product_ships(page) -> bool:
    """Whether the page is about a product that goes out in a parcel.

    A booked service or a download is not returned by post; neither is a
    listing that is not a catalog product (a hotel, an experience row).
    """
    obj = getattr(page, 'obj', None)
    if obj is None or getattr(obj, 'product_type', '') == 'service':
        return False
    return bool(getattr(obj, 'requires_shipping', False))


def store_ships_goods() -> bool:
    """Whether the store sells anything that ships."""
    from django.apps import apps

    try:
        product = apps.get_model('catalog', 'Product')
        return product.objects.shoppable().filter(requires_shipping=True).exists()
    except Exception:  # noqa: BLE001 — no catalog, or an unmigrated DB during a deploy
        return False


def _store_country() -> str:
    """The merchant's own country, from Settings → General."""
    try:
        from core.models import StoreSettings

        store = StoreSettings.objects.first()
        return (getattr(store, 'country', '') or '').strip().upper()[:2]
    except Exception:  # noqa: BLE001 — unmigrated DB during a deploy
        return ''


def _product_offers(graph) -> list[dict]:
    """Every offer on the graph's Product nodes, variants' included.

    A product with several editions is a ProductGroup whose offers sit on its
    `hasVariant` members, not on the group.
    """
    if not isinstance(graph, dict):
        return []
    found: list[dict] = []

    def collect(node):
        offers = node.get('offers')
        for offer in offers if isinstance(offers, list) else [offers]:
            if isinstance(offer, dict):
                found.append(offer)
        for member in node.get('hasVariant') or []:
            if isinstance(member, dict):
                collect(member)

    for node in graph.get('@graph') or []:
        if isinstance(node, dict) and 'Product' in str(node.get('@type', '')):
            collect(node)
    return found


def _store_node(graph) -> dict | None:
    """The graph's node for the store itself (seo names it `…#organization`)."""
    if not isinstance(graph, dict):
        return None
    for node in graph.get('@graph') or []:
        if isinstance(node, dict) and str(node.get('@id', '')).endswith('#organization'):
            return node
    return None
