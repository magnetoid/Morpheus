"""Product gallery plugin — square carousel partial for PDPs.

Ships a single template, `product_gallery/_carousel.html`, that any
theme can include in its product-detail template:

    {% include "product_gallery/_carousel.html" with
       images=product.images
       alt=product.name
       slug=product.slug %}

Native CSS scroll-snap. Square aspect ratio. Dot indicators. Prev/next
buttons. Keyboard arrows. No JS framework, no model.
"""
from __future__ import annotations

import logging

from morpheus import Plugin

logger = logging.getLogger('morpheus.product_gallery')


class ProductGalleryPlugin(Plugin):
    name = "product_gallery"
    label = "Product Gallery"
    version = "1.0.0"
    description = (
        "Square-format scroll-snap product image carousel — drop-in "
        "template partial for any storefront theme."
    )
    has_models = False
    requires = ['catalog']
