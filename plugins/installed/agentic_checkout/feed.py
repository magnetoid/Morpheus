"""ACP product feed (openapi.feed.yaml).

Reuses ``google_shopping``'s ``map_product()`` field logic (price/image/
identifiers/availability/brand — the single source of truth for feed-field
resolution), reshaped to ACP feed fields:

    id, title, description, link, image_link, price, currency, availability,
    gtin, brand, item_group_id (for variants).

Read-only and Bearer/scope-gated (``catalog.read``). Advertised in
``/.well-known/acp.json``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from plugins.installed.agentic_checkout.auth import require_acp_scope
from plugins.installed.agentic_checkout.plugin import ACP_API_VERSION

logger = logging.getLogger('morpheus.agentic_checkout')

_FEED_LIMIT = 1000


@dataclass(frozen=True)
class _DefaultFeedSettings:
    """Minimal stand-in for google_shopping's FeedSettings — only the fields
    ``map_product`` reads. Used when google_shopping is disabled/absent."""

    include_out_of_stock: bool = True
    default_brand: str = ''
    default_condition: str = 'new'
    default_google_product_category: str = ''
    language: str = 'en'


def _resolve_feed_settings():
    try:
        from plugins.installed.google_shopping.services.settings import feed_settings

        return feed_settings()
    except Exception:  # noqa: BLE001 — google_shopping disabled → use defaults
        return _DefaultFeedSettings()


def _google_to_acp(item: dict) -> dict[str, Any]:
    """Reshape a google_shopping feed-attr dict into ACP feed fields.

    Google's ``price`` is ``'9.00 USD'``; ACP wants a numeric ``price`` plus a
    separate ``currency``. ``availability`` maps in_stock/out_of_stock directly.
    """
    price_raw = (item.get('sale_price') or item.get('price') or '').strip()
    price, currency = '', ''
    if price_raw:
        parts = price_raw.split()
        price = parts[0]
        currency = parts[1] if len(parts) > 1 else ''
    out: dict[str, Any] = {
        'id': item.get('id', ''),
        'title': item.get('title', ''),
        'description': item.get('description', ''),
        'link': item.get('link', ''),
        'image_link': item.get('image_link', ''),
        'price': price,
        'currency': currency,
        'availability': item.get('availability', 'in_stock'),
    }
    if item.get('gtin'):
        out['gtin'] = item['gtin']
    if item.get('brand'):
        out['brand'] = item['brand']
    if item.get('item_group_id'):
        out['item_group_id'] = item['item_group_id']
    return out


@csrf_exempt
@require_http_methods(['GET'])
def product_feed(request: HttpRequest) -> HttpResponse:
    """GET /acp/feed.json — ACP product feed for active products."""
    denied = require_acp_scope(request, 'catalog.read')
    if denied is not None:
        denied['API-Version'] = ACP_API_VERSION
        return denied

    from plugins.installed.catalog.models import Product

    try:
        from plugins.installed.google_shopping.services.mapping import (
            expand_variants,
            map_product,
        )
    except ImportError:
        # google_shopping disabled/absent → serve a valid, empty typed feed
        # rather than 500. (It is a hard `requires`, so this only happens if a
        # merchant force-disables it.)
        logger.warning('agentic_checkout: google_shopping mapping unavailable; empty feed')
        empty = JsonResponse({'version': ACP_API_VERSION, 'products': [], 'count': 0})
        empty['API-Version'] = ACP_API_VERSION
        return empty

    settings = _resolve_feed_settings()
    products = Product.objects.filter(status='active').order_by('-id')[:_FEED_LIMIT]

    items: list[dict[str, Any]] = []
    for product in products:
        base = map_product(product, settings)
        if base is None:
            continue
        variants = expand_variants(product, base, settings)
        if variants:
            items.extend(_google_to_acp(v) for v in variants)
        else:
            items.append(_google_to_acp(base))

    response = JsonResponse({'version': ACP_API_VERSION, 'products': items, 'count': len(items)})
    response['API-Version'] = ACP_API_VERSION
    return response
