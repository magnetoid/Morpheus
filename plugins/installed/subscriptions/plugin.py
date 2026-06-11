"""Subscriptions plugin manifest."""

from __future__ import annotations

from morpheus import DashboardPage, Plugin


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

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.subscriptions.urls',
            prefix='dashboard/subscriptions/',
            namespace='subscriptions',
        )

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Subscriptions',
                slug='subscriptions',
                view='plugins.installed.subscriptions.views.subscriptions_dashboard',
                icon='repeat',
                section='customers',
                order=70,
            ),
        ]
