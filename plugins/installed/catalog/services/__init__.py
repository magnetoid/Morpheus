"""Catalog services — shared write helpers for the MCP tool layer
and the GraphQL mutations.

This package replaces the original 896-LOC ``services.py`` monolith
(commit-history-traceable at ``f775aa8^:plugins/installed/catalog/services.py``).
The split is layered by feature area; external callers keep importing
from ``plugins.installed.catalog.services`` unchanged thanks to the
re-exports below.

  * _helpers.py    — constants, PublishError, URL+download primitives,
                     slug/SKU uniquifiers, price coercer, serializers,
                     variant-field applier. Private.
  * products.py    — publish_digital_product, create/update/archive/
                     restore/delete product, update_digital_pdf.
  * categories.py  — create/update/archive category.
  * images.py      — add/remove/set-primary product image.
  * variants.py    — create + update variant.
"""

from __future__ import annotations

# Public exception type.
from ._helpers import PublishError

# Categories.
from .categories import (
    archive_category,
    create_category,
    update_category,
)

# Images.
from .images import (
    add_product_image,
    remove_product_image,
    set_primary_image,
)

# Product CRUD + publishing.
from .products import (
    archive_product,
    create_product,
    delete_product,
    publish_digital_product,
    restore_product,
    update_digital_pdf,
    update_product,
)

# Variants.
from .variants import (
    create_variant,
    update_variant,
)

__all__ = [
    'PublishError',
    # products
    'publish_digital_product',
    'create_product',
    'update_product',
    'archive_product',
    'restore_product',
    'delete_product',
    'update_digital_pdf',
    # categories
    'create_category',
    'update_category',
    'archive_category',
    # images
    'add_product_image',
    'remove_product_image',
    'set_primary_image',
    # variants
    'create_variant',
    'update_variant',
]
