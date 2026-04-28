"""Subscriptions plugin manifest."""
from __future__ import annotations

from morpheus import Plugin


class SubscriptionsPlugin(Plugin):
    name = 'subscriptions'
    label = 'Subscriptions'
    version = '1.0.0'
    description = (
        'Recurring billing: Plan, Subscription, SubscriptionInvoice. '
        'Manual provider out of the box; Stripe Billing adapter slot ready.'
    )
    has_models = True
    requires = ['customers']
