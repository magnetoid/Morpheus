"""Reviews plugin manifest."""
from __future__ import annotations

from morpheus import DashboardPage, Plugin, StorefrontBlock


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
            'plugins.installed.reviews.urls', prefix='reviews/', namespace='reviews',
        )
        # Merchant moderation surface.
        self.register_urls(
            'plugins.installed.reviews.urls_dashboard',
            prefix='dashboard/reviews/', namespace='reviews_dashboard',
        )

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
