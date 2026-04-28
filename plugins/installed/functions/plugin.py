"""Morph Functions plugin manifest."""
from __future__ import annotations

import logging

from morpheus import events
from morpheus import Plugin

logger = logging.getLogger('morpheus.functions')


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

        self.register_hook(
            events.PRODUCT_CALCULATE_PRICE,
            self.on_calculate_price,
            priority=40,  # before AI dynamic pricing (50) so merchant rules win first
        )
        self.register_hook(
            events.CART_CALCULATE_TOTAL,
            self.on_calculate_cart_total,
            priority=40,
        )

    def on_calculate_price(self, value, product=None, customer=None, **kwargs):
        """Run all enabled `product.calculate_price` functions in priority order."""
        from plugins.installed.functions.services import dispatch_filter

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

    def on_calculate_cart_total(self, value, cart=None, **kwargs):
        from plugins.installed.functions.services import dispatch_filter

        return dispatch_filter(
            target='cart.calculate_total',
            value=value,
            input={
                'cart_id': str(cart.id) if cart else None,
                'subtotal': str(getattr(value, 'amount', value)),
                'currency': str(getattr(value, 'currency', 'USD')),
            },
        )
