"""ACP product feed (``spec/2026-04-17/openapi/openapi.feed.yaml``).

Reuses ``google_shopping``'s ``map_product()`` field logic (price/image/
identifiers/availability/brand — the single source of truth for feed-field
resolution), reshaped to the specification's feed document: a list of
``Product`` groups, each with its ``variants``::

    products[]: id, title, description {plain}, url, media[], variants[]
    variants[]: id, title, url, price {amount (minor units), currency},
                list_price, availability {available, status}, condition[],
                media[], barcodes[], variant_options[], categories[], seller

Until v0.88.1 the feed wrote the ``2025-09-29`` rows (``link``, ``image_link``,
``price`` as a string beside ``currency``) under a ``2026-04-17`` header.
``is_eligible_checkout`` on each product is a Morpheus extension (the
per-product ``agentic.exclude`` metafield); consumers ignore unknown members.

Read-only and Bearer/scope-gated (``catalog.read``). Advertised in
``/.well-known/acp.json``.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from plugins.installed.agentic_checkout.app import ACP_API_VERSION
from plugins.installed.agentic_checkout.auth import require_acp_scope
from plugins.installed.agentic_checkout.eligibility import agentic_excluded

logger = logging.getLogger('morpheus.agentic_checkout')

_FEED_LIMIT = 1000

#: Google feed availability → the specification's ``Availability.status``.
_STATUS = {
    'in_stock': 'in_stock',
    'out_of_stock': 'out_of_stock',
    'preorder': 'preorder',
    'backorder': 'backorder',
}


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


def _price(raw: str) -> dict[str, Any] | None:
    """``'9.00 USD'`` → ``{'amount': 900, 'currency': 'USD'}`` (minor units,
    by the currency's own sub-unit so JPY is not multiplied by 100)."""
    parts = (raw or '').split()
    if len(parts) != 2:
        return None
    try:
        amount = Decimal(parts[0])
    except InvalidOperation:
        return None
    currency = parts[1].upper()
    sub_unit = 100
    with contextlib.suppress(Exception):  # an unknown code keeps cents
        from moneyed import get_currency

        sub_unit = int(get_currency(currency).sub_unit or 100)
    return {'amount': int((amount * sub_unit).to_integral_value()), 'currency': currency}


def _seller(base: str) -> dict[str, Any]:
    from core.utils.site import store_name

    links = [
        {'type': 'homepage', 'url': f'{base}/'},
        {'type': 'privacy_policy', 'url': f'{base}/p/privacy/'},
        {'type': 'terms_of_service', 'url': f'{base}/p/terms/'},
        {'type': 'returns', 'url': f'{base}/returns/'},
    ]
    return {'name': store_name(), 'links': links}


def _variant(item: dict, *, seller: dict, option: str = '') -> dict[str, Any]:
    """One ``Variant`` from a google_shopping feed row."""
    regular = _price(item.get('price') or '')
    sale = _price(item.get('sale_price') or '')
    status = _STATUS.get(str(item.get('availability') or 'in_stock'), 'in_stock')
    out: dict[str, Any] = {
        'id': item.get('id', ''),
        'title': item.get('title', ''),
        'availability': {
            'available': status in ('in_stock', 'preorder', 'backorder'),
            'status': status,
        },
        'seller': seller,
    }
    if item.get('link'):
        out['url'] = item['link']
    if sale and regular:
        out['price'], out['list_price'] = sale, regular
    elif regular:
        out['price'] = regular
    if item.get('description'):
        out['description'] = {'plain': item['description']}
    if item.get('image_link'):
        out['media'] = [{'type': 'image', 'url': item['image_link']}]
    if item.get('condition'):
        out['condition'] = [str(item['condition'])]
    if item.get('gtin'):
        out['barcodes'] = [{'type': 'gtin', 'value': str(item['gtin'])}]
    elif item.get('mpn'):
        out['barcodes'] = [{'type': 'mpn', 'value': str(item['mpn'])}]
    if item.get('google_product_category'):
        out['categories'] = [{'value': item['google_product_category'], 'taxonomy': 'google'}]
    if option:
        out['variant_options'] = [{'name': 'variant', 'value': option}]
    return out


def _product(base: dict, variants: list[dict], *, eligible: bool) -> dict[str, Any]:
    out: dict[str, Any] = {
        'id': base.get('item_group_id') or base.get('id', ''),
        'title': base.get('title', ''),
        'variants': variants,
        'is_eligible_checkout': eligible,
    }
    if base.get('link'):
        out['url'] = base['link']
    if base.get('description'):
        out['description'] = {'plain': base['description']}
    if base.get('image_link'):
        out['media'] = [{'type': 'image', 'url': base['image_link']}]
    return out


def _option_name(row: dict, base: dict) -> str:
    """The variant's own name: ``expand_variants`` appends it to the title."""
    title, base_title = row.get('title') or '', base.get('title') or ''
    if title.startswith(base_title) and ' — ' in title:
        return title.rsplit(' — ', 1)[-1].strip()
    return ''


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
    seller = _seller(request.build_absolute_uri('/').rstrip('/'))
    products = Product.objects.filter(status='active').order_by('-id')[:_FEED_LIMIT]

    groups: list[dict[str, Any]] = []
    for product in products:
        base = map_product(product, settings)
        if base is None:
            continue
        rows = expand_variants(product, base, settings)
        if rows:
            variants = [_variant(r, seller=seller, option=_option_name(r, base)) for r in rows]
        else:
            variants = [_variant(base, seller=seller)]
        # Per-product agent-checkout eligibility (metafield ``agentic.exclude``).
        groups.append(_product(base, variants, eligible=not agentic_excluded(product)))

    response = JsonResponse({'version': ACP_API_VERSION, 'products': groups, 'count': len(groups)})
    response['API-Version'] = ACP_API_VERSION
    return response
