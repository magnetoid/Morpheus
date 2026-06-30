"""Channel resolver + per-channel price lookup.

Public surface:

    from core.channels import (
        current_channel, price_for, listing_for, list_published_in_channel,
    )

`current_channel(request)` returns the StoreChannel matching the request's
host (falls back to default). `price_for(product, channel)` returns a
djmoney `Money` — channel listing if present, else product.price.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger('morpheus.channels')

_UNSET = object()  # sentinel for the per-request channel memo


def current_channel(request) -> Any:
    from core.models import StoreChannel

    # Resolve once per request. Several context processors (display_currency,
    # channel_context) each call this on every request — without memoizing we'd
    # run StoreChannel.resolve_for_request (1-2 queries) two+ times for the same
    # answer. Cache on the request object: per-request scope means no cross-
    # request staleness and nothing to invalidate.
    if request is None:
        return StoreChannel.resolve_for_request(None)
    cached = getattr(request, '_morph_current_channel', _UNSET)
    if cached is _UNSET:
        cached = StoreChannel.resolve_for_request(request)
        request._morph_current_channel = cached
    return cached


def listing_for(product, channel) -> Any | None:
    if product is None or channel is None:
        return None
    from core.models import ProductChannelListing

    try:
        ct = ContentType.objects.get_for_model(type(product))
    except Exception:  # noqa: BLE001
        return None
    return ProductChannelListing.objects.filter(
        channel=channel,
        product_ct=ct,
        product_id=str(product.pk),
    ).first()


def price_for(product, channel):
    """Return Money — channel-listing override if present, else product.price."""
    if product is None:
        return None
    listing = listing_for(product, channel) if channel is not None else None
    base = getattr(product, 'price', None)
    if listing is None or listing.price_amount is None:
        return base
    try:
        from djmoney.money import Money

        currency = (
            channel.currency
            if channel
            else (str(getattr(base, 'currency', 'USD')) if base else 'USD')
        )
        return Money(Decimal(str(listing.price_amount)), currency)
    except Exception:  # noqa: BLE001
        return base


def list_published_in_channel(channel, *, limit: int = 24):
    """List products published in `channel` (visible_in_listings=True).

    Returns a list of dicts (product_id, price_amount). Plugins can hydrate
    the actual Product objects.
    """
    from core.models import ProductChannelListing

    qs = ProductChannelListing.objects.filter(
        channel=channel,
        is_published=True,
        visible_in_listings=True,
    ).order_by('-published_at', '-updated_at')[:limit]
    return [
        {
            'product_id': r.product_id,
            'price_amount': r.price_amount,
            'available_for_purchase': r.available_for_purchase,
        }
        for r in qs
    ]
