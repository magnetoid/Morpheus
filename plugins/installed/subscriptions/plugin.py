"""Subscriptions plugin manifest."""

from __future__ import annotations

from morpheus import DashboardPage, Plugin, StorefrontBlock, events


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
        # Storefront membership page (plans + subscribe) + the member discount.
        self.register_urls(
            'plugins.installed.subscriptions.urls_storefront',
            prefix='',
            namespace='subscriptions_storefront',
        )
        # Apply the member discount at checkout (live CART_CALCULATE_BREAKDOWN
        # filter — the per-product price hook is dead). Priority 40 = before
        # tax/shipping handlers that read the discounted total.
        from plugins.installed.subscriptions.membership import apply_member_discount

        self.register_hook(events.CART_CALCULATE_BREAKDOWN, apply_member_discount, priority=40)

    def contribute_storefront_blocks(self) -> list:
        # "Membership" link in the footer's "pages" column (footer_extra slot).
        # Contributed, so it vanishes when the plugin is disabled.
        return [
            StorefrontBlock(
                slot='footer_extra',
                template='subscriptions/blocks/footer_link.html',
                priority=50,
            ),
        ]

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

    def contribute_agent_tools(self) -> list:
        from plugins.installed.subscriptions.agent_tools import (
            subscriptions_cancel_tool,
            subscriptions_list_tool,
            subscriptions_pause_tool,
            subscriptions_resume_tool,
        )

        return [
            subscriptions_list_tool,
            subscriptions_pause_tool,
            subscriptions_resume_tool,
            subscriptions_cancel_tool,
        ]
