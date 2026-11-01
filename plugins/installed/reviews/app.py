"""Reviews plugin manifest."""

from __future__ import annotations

from morpheus.app import DashboardPage, Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events


class ReviewsPlugin(Plugin):
    name = 'reviews'
    label = 'Reviews'
    version = '0.3.0'
    description = (
        "Customer reviews on the PDP, a buyer's published at once and anyone "
        "else's after moderation at /dashboard/reviews/, plus the rating, "
        'verified-buyer and recent-purchases strip under the price.'
    )
    has_models = True
    requires = ['catalog', 'orders']

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
            # The trust strip (the trust_signals app until v0.129.0). The
            # block fetches its data through the `trust_data` tag.
            StorefrontBlock(
                slot='pdp_below_price',
                template='reviews/blocks/trust_strip.html',
                priority=30,  # ahead of low_stock_badge (priority=20)
                context_keys=['product'],
            ),
        ]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'show_rating': {
                    'type': 'boolean',
                    'title': 'Show star rating + review count',
                    'default': True,
                },
                'min_reviews_for_rating': {
                    'type': 'integer',
                    'title': 'Minimum reviews before showing rating',
                    'minimum': 0,
                    'maximum': 100,
                    'default': 3,
                    'description': (
                        'Hide the rating until the product has at least this '
                        'many reviews. Low-N ratings hurt trust more than '
                        'they help.'
                    ),
                },
                'show_verified_share': {
                    'type': 'boolean',
                    'title': 'Show verified-buyer percentage',
                    'default': True,
                },
                'show_recent_purchases': {
                    'type': 'boolean',
                    'title': 'Show recent-purchases ticker',
                    'default': True,
                },
                'recent_purchases_window_hours': {
                    'type': 'integer',
                    'title': 'Recent-purchases lookback (hours)',
                    'minimum': 1,
                    'maximum': 168,
                    'default': 72,
                    'description': '"X ordered in the last N hours". 72h is the sweet spot.',
                },
                'min_recent_purchases': {
                    'type': 'integer',
                    'title': 'Minimum recent purchases to show the ticker',
                    'minimum': 1,
                    'maximum': 100,
                    'default': 3,
                    'description': (
                        'Hide the ticker if fewer than N people bought it. '
                        '"1 ordered today" reads as desperate, not popular.'
                    ),
                },
            },
        }

    def contribute_settings_panel(self) -> SettingsPanel:
        # trust_signals passed the properties without the object wrapper, so
        # its panel rendered no fields at all (v0.129.0 fixed it in the move).
        return SettingsPanel(
            label='Reviews',
            category='storefront',
            description="Which review and purchase signals show under a product's price.",
            schema=self.get_config_schema(),
        )

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
