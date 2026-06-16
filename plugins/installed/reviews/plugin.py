"""Reviews plugin manifest."""

from __future__ import annotations

from morpheus import Plugin, StorefrontBlock, events


class ReviewsPlugin(Plugin):
    name = 'reviews'
    label = 'Reviews'
    version = '0.2.0'
    description = (
        'Customer reviews on the PDP. Auto-published on submit. '
        'Merchant moderation lives at /dashboard/reviews/.'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        # Storefront write endpoint.
        self.register_urls(
            'plugins.installed.reviews.urls',
            prefix='reviews/',
            namespace='reviews',
        )
        # Merchant moderation surface.
        self.register_urls(
            'plugins.installed.reviews.urls_dashboard',
            prefix='dashboard/reviews/',
            namespace='reviews_dashboard',
        )

        # Contribute new-review activity to the dashboard home feed.
        self.register_hook(events.ACTIVITY_FEED, self.on_activity_feed, priority=40)

    def on_activity_feed(self, value, limit=20, **kwargs):
        """Fold recent reviews into the dashboard home feed
        (``ACTIVITY_FEED`` filter). Append own items, return the list.
        """
        from plugins.installed.catalog.models import Review  # noqa: PLC0415

        qs = Review.objects.select_related('product', 'customer').order_by('-created_at')
        for r in qs[:limit]:
            who = r.customer.email if r.customer else 'a reader'
            value.append(
                {
                    'kind': 'review',
                    'icon': 'star',
                    'label': f'New review on {r.product.name} ({r.rating}/5)',
                    'hint': f'by {who}',
                    'url': '/dashboard/reviews/',
                    'when': r.created_at,
                }
            )
        return value

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='pdp_below_form',
                template='reviews/blocks/write_review.html',
                priority=80,
            ),
        ]

    def contribute_dashboard_pages(self) -> list:
        # No DashboardPage — Reviews lives at /dashboard/reviews/ via
        # register_urls above, and the sidebar entry is hardcoded under
        # Products in admin_dashboard/base.html. The previous
        # nav='hidden' DashboardPage existed only to surface a card in
        # the /dashboard/apps/ tile grid; removing it kills that one
        # tile but the plugin remains active and reachable.
        return []

    def contribute_agent_tools(self) -> list:
        from plugins.installed.reviews.agent_tools import (
            reviews_approve_tool,
            reviews_delete_tool,
            reviews_list_pending_tool,
        )

        return [reviews_list_pending_tool, reviews_approve_tool, reviews_delete_tool]
