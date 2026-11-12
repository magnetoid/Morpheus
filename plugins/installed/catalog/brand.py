"""A product's brand, from one source (v0.163.0).

Every surface that names a brand (the product page's structured data and every
channel feed) asks here. An app that knows a product's brand answers
`PRODUCT_BRAND` (book_product: the publisher); failing that, the store-wide
`default_brand` on catalog's settings, which the merchant sets when they make
or label what they sell. Nothing else is a brand: product_safety's
manufacturer is who answers for a product, and a vendor is who sells it.
With neither, there is no brand, and a surface that needs one says nothing.
"""

from __future__ import annotations

import logging

logger = logging.getLogger('morpheus.catalog')

#: Google and Meta cap a brand at 70 and 100 characters.
MAX_LENGTH = 70


def default_brand() -> str:
    """The store-wide brand the merchant set on catalog's settings, or ''."""
    try:
        from plugins.registry import app_registry

        plugin = app_registry.get('catalog')
        value = plugin.get_config_value('default_brand', '') if plugin else ''
    except Exception:  # noqa: BLE001 — an unmigrated DB during a deploy
        return ''
    return str(value or '').strip()[:MAX_LENGTH]


def product_brand(product) -> str:
    """The brand of one product (a catalog Product row), or '' when none is known."""
    if product is None:
        return ''
    name = ''
    try:
        from core.hooks import MorpheusEvents, hook_registry

        name = hook_registry.filter(MorpheusEvents.PRODUCT_BRAND, '', product=product)
    except Exception as e:  # noqa: BLE001 — a bad answer must not lose the page or the feed
        logger.debug('catalog: PRODUCT_BRAND failed: %s', e)
    name = str(name or '').strip()[:MAX_LENGTH] if isinstance(name, str) else ''
    return name or default_brand()
