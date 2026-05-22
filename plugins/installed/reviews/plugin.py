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
        # The hardcoded "Reviews" link under Products in the dashboard
        # base.html already covers the nav entry — and points at the
        # canonical /dashboard/reviews/ URL, not /dashboard/apps/reviews/
        # reviews/. We still register the DashboardPage so the registry
        # can resolve the view + the page shows up in /dashboard/apps/
        # tile grids, but mark nav='hidden' to avoid a duplicate sidebar
        # link — and parent under the catalog section if it ever does
        # render.
        return [
            DashboardPage(
                label='Reviews',
                slug='reviews',
                view='plugins.installed.reviews.dashboard.reviews_list',
                icon='star',
                section='catalog',
                order=60,
                nav='hidden',
            ),
        ]
