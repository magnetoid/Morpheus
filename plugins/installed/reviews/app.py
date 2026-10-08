"""Reviews plugin manifest."""

from __future__ import annotations

from morpheus.app import DashboardPage, Plugin, StorefrontBlock
from morpheus.core import events


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
        # The Reviews tab of the Products section, linking the moderation
        # queue at /dashboard/reviews/ (register_urls above). The shell used
        # to hardcode the link; contributed, it leaves with the app.
        return [
            DashboardPage(
                label='Reviews',
                slug='reviews',
                view='plugins.installed.reviews.dashboard.reviews_list',
                icon='star',
                section='products',
                order=50,
                url='/dashboard/reviews/',
            )
        ]

    def contribute_agent_tools(self) -> list:
        from plugins.installed.reviews.agent_tools import (
            reviews_approve_tool,
            reviews_delete_tool,
            reviews_list_pending_tool,
        )

        return [reviews_list_pending_tool, reviews_approve_tool, reviews_delete_tool]
