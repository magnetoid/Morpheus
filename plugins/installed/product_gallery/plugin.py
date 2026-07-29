"""Product gallery plugin — main cover + square slider for PDPs.

Ships three templates the theme can use:

    {% include "product_gallery/_main_cover.html" with
       product=product alt=product.name slug=product.slug %}

      → renders ONLY the primary image as the cover. Single hero.

    `product_gallery/_slider.html` is contributed as a StorefrontBlock
    into the `pdp_above_long_description` slot at priority=20, so it
    auto-renders above the product video block (which sits at
    priority=50 in the same slot). Shows every non-primary image as a
    square scroll-snap strip.

    `product_gallery/_carousel.html` is the legacy combined carousel
    (kept for back-compat with themes that include it directly).

Native CSS scroll-snap. No JS framework, no model.
"""

from __future__ import annotations

import logging

from morpheus.plugin import Plugin, StorefrontBlock

logger = logging.getLogger('morpheus.product_gallery')


class ProductGalleryPlugin(Plugin):
    name = 'product_gallery'
    label = 'Product Gallery'
    version = '1.1.0'
    description = (
        'Main cover (primary image) + square slider (non-primary images) '
        'for PDPs. Native scroll-snap, no JS dep.'
    )
    has_models = False
    requires = ['catalog']

    def contribute_storefront_blocks(self) -> list:
        return [
            # Slider renders ABOVE the video block (priority=50) and ABOVE
            # the long description. Hides itself when there are no
            # non-primary images.
            StorefrontBlock(
                slot='pdp_above_long_description',
                template='product_gallery/_slider.html',
                priority=20,
                context_keys=['product'],
            ),
        ]
