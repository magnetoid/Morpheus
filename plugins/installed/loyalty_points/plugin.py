"""Loyalty points plugin manifest."""
from __future__ import annotations

from morpheus import Plugin


class LoyaltyPointsPlugin(Plugin):
    name = 'loyalty_points'
    label = 'Loyalty points'
    version = '0.1.0'
    description = (
        'Earn 1 point per currency unit on paid orders. Balance shown '
        'on the customer account page. Redemption at checkout deferred.'
    )
    has_models = True
    requires = ['orders', 'customers']
