"""Promotions plugin manifest."""
from __future__ import annotations

import logging

from morpheus import Plugin
from morpheus import DashboardPage

logger = logging.getLogger('morpheus.promotions')


class PromotionsPlugin(Plugin):
    name = 'promotions'
    label = 'Promotions'
    version = '1.0.0'
    description = (
        'Rule-based promotion engine: stack predicates (cart total, channel, '
        'country, customer group, product) with actions (% off, fixed off, '
        'free shipping, gift). Channel-scoped, time-bounded, audit-logged.'
    )
    has_models = True
    requires = ['orders']

    def ready(self) -> None:
        from morpheus import events
        self.register_hook(events.CART_CALCULATE_TOTAL, self.on_cart_total, priority=10)
        self.register_urls(
            'plugins.installed.promotions.urls',
            prefix='dashboard/promotions/',
            namespace='promotions',
        )

    def on_cart_total(self, value, cart=None, channel=None, customer=None,
                      address=None, coupon=None, **kwargs):
        if cart is None or value is None:
            return value
        try:
            from plugins.installed.promotions.services import evaluate
            country = (address or {}).get('country', '') if address else ''
            applied = evaluate(cart, channel=channel, customer=customer,
                               country=country, coupon=coupon)
            if not applied:
                return value
            from decimal import Decimal
            discount = sum((a.discount_amount for a in applied), Decimal('0'))
            if not discount:
                return value
            try:
                amount_attr = getattr(value, 'amount', None)
                if amount_attr is not None:
                    new_amount = max(Decimal('0'), Decimal(str(amount_attr)) - discount)
                    return type(value)(new_amount, value.currency)
            except Exception:  # noqa: BLE001
                pass
            return value
        except Exception as e:  # noqa: BLE001
            logger.warning('promotions: on_cart_total failed: %s', e, exc_info=True)
            return value

    def contribute_agent_tools(self) -> list:
        from plugins.installed.promotions.agent_tools import (
            create_percent_off_tool, list_promotions_tool,
        )
        return [list_promotions_tool, create_percent_off_tool]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                slug='index',
                label='Promotions',
                section='marketing',
                icon='ticket',
                view='plugins.installed.promotions.views.promotions_index',
                order=20,
            ),
        ]

    # No settings panel — promotions are operational data, not config.
    # All knobs (priority, channel scope, coupon gate) live on each Promotion row.
