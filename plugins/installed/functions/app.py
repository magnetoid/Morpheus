"""Morph Functions plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import Plugin
from morpheus.core import events

logger = logging.getLogger('morpheus.functions')

# 5-minute cache for the "any Function rows exist?" gate. Avoids a DB hit
# on every PRODUCT_CALCULATE_PRICE / CART_CALCULATE_BREAKDOWN fan-out
# while the Functions table is empty (the common case until merchants
# author their first function).
_HAS_FUNCTIONS_CACHE_KEY = 'morpheus:functions:has_any'
_HAS_FUNCTIONS_CACHE_TTL = 300  # seconds (5 min)


def _has_any_functions() -> bool:
    """Cached `Function.objects.exists()` — 5-minute Redis TTL."""
    from django.core.cache import cache  # noqa: PLC0415

    cached = cache.get(_HAS_FUNCTIONS_CACHE_KEY)
    if cached is not None:
        return bool(cached)
    try:
        from plugins.installed.functions.models import Function  # noqa: PLC0415

        exists = Function.objects.exists()
    except Exception:  # noqa: BLE001 — table may not be migrated yet
        exists = False
    cache.set(_HAS_FUNCTIONS_CACHE_KEY, exists, _HAS_FUNCTIONS_CACHE_TTL)
    return exists


class FunctionsPlugin(Plugin):
    name = 'functions'
    label = 'Functions Runtime'
    version = '0.1.0'
    description = (
        'Sandboxed merchant-defined functions for cart totals, product '
        'pricing, shipping rates, order validation.'
    )
    has_models = True

    def ready(self) -> None:
        self.register_graphql_extension('plugins.installed.functions.graphql.queries')
        self.register_graphql_extension('plugins.installed.functions.graphql.mutations')

        if not _has_any_functions():
            logger.info(
                'functions: no Function rows; fan-out is no-op until a Function is created.'
            )

        self.register_hook(
            events.PRODUCT_CALCULATE_PRICE,
            self.on_calculate_price,
            priority=40,  # before AI dynamic pricing (50) so merchant rules win first
        )
        # Subscribe to the canonical cart filter — runs both new
        # `cart.calculate_breakdown` user functions and legacy
        # `cart.calculate_total` ones for back-compat.
        self.register_hook(
            events.CART_CALCULATE_BREAKDOWN,
            self.on_calculate_cart_breakdown,
            priority=40,
        )

    def on_calculate_price(self, value, product=None, customer=None, **kwargs):
        """Run all enabled `product.calculate_price` functions in priority order."""
        if not _has_any_functions():
            return value
        from plugins.installed.functions.services import dispatch_filter  # noqa: PLC0415

        return dispatch_filter(
            target='product.calculate_price',
            value=value,
            input={
                'product_id': str(product.id) if product else None,
                'customer_id': str(customer.id) if customer else None,
                'price': str(getattr(value, 'amount', value)),
                'currency': str(getattr(value, 'currency', 'USD')),
            },
            channel=getattr(product, 'channel', None) if product else None,
        )

    def on_calculate_cart_breakdown(self, value, cart=None, **kwargs):
        """Dispatch user functions targeting either the new breakdown
        event or the legacy total event. Legacy functions only see the
        subtotal in their input — they were written before BREAKDOWN
        existed."""
        if not _has_any_functions():
            return value
        from plugins.installed.functions.services import dispatch_filter  # noqa: PLC0415

        # Common payload — all keys present on the canonical breakdown.
        currency = ((value or {}).get('currency') if isinstance(value, dict) else None) or 'USD'
        subtotal = None
        if isinstance(value, dict):
            sub = value.get('subtotal')
            subtotal = str(getattr(sub, 'amount', sub or '0'))

        # New target.
        value = dispatch_filter(
            target='cart.calculate_breakdown',
            value=value,
            input={
                'cart_id': str(cart.id) if cart else None,
                'subtotal': subtotal,
                'currency': currency,
            },
        )

        # Legacy target — runs against the same value so existing
        # functions that wrote to `cart.calculate_total` keep working.
        value = dispatch_filter(
            target='cart.calculate_total',
            value=value,
            input={
                'cart_id': str(cart.id) if cart else None,
                'subtotal': subtotal,
                'currency': currency,
            },
        )
        return value
