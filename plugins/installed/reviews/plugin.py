"""Reviews plugin manifest."""
from __future__ import annotations

from morpheus import Plugin, StorefrontBlock


class ReviewsPlugin(Plugin):
    name = 'reviews'
    label = 'Reviews'
    version = '0.1.0'
    description = (
        'Customer reviews on the PDP. Auto-published on submit; '
        'merchant can hide / re-publish via the Django admin.'
    )
    has_models = True
    requires = ['catalog']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.reviews.urls', prefix='reviews/', namespace='reviews',
        )

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='pdp_below_form',
                template='reviews/blocks/write_review.html',
                priority=80,
            ),
        ]
