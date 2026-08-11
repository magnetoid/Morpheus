"""Product videos plugin manifest."""

from __future__ import annotations

from morpheus.app import Plugin, StorefrontBlock


class ProductVideosPlugin(Plugin):
    name = 'product_videos'
    label = 'Product videos'
    version = '0.1.0'
    description = (
        'Attach one or more videos to a product. Rendered on the storefront PDP '
        'just above the long description. Auto-embeds YouTube + Vimeo URLs; '
        'falls back to raw <iframe> HTML for anything unusual. Edit via Django admin.'
    )
    has_models = True
    requires = ['catalog']

    def contribute_storefront_blocks(self) -> list:
        return [
            StorefrontBlock(
                slot='pdp_above_long_description',
                template='product_videos/blocks/pdp_videos.html',
                priority=50,
                context_keys=['product'],
            ),
        ]
