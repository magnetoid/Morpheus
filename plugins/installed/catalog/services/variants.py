"""Variant write operations — create + update.

Shopify-parity surface: each variant carries its own ``variant_type``
(physical / digital / virtual), price, compare-at, requires_shipping,
inventory policy, barcode, and free-text size. Most of the heavy
lifting lives in :func:`_apply_variant_fields` (in ``_helpers``) which
both create + update share.
"""
from __future__ import annotations

from django.db import transaction

from ._helpers import (
    PublishError,
    _apply_variant_fields,
    _serialize_variant,
    logger,
)


@transaction.atomic
def create_variant(*, product_slug: str, **fields) -> dict:
    """Create a new ProductVariant on the given product. Required:
    ``name`` + ``sku``. Every other field is optional and follows the
    same semantics as :func:`update_variant`."""
    from plugins.installed.catalog.models import Product, ProductVariant

    product = Product.objects.filter(slug=product_slug).first()
    if product is None:
        raise PublishError(f'product slug {product_slug!r} not found')

    variant = ProductVariant(product=product)
    if 'name' not in fields:
        raise PublishError('name is required')
    if 'sku' not in fields:
        raise PublishError('sku is required')
    _apply_variant_fields(variant, fields)
    variant.save()
    logger.info('catalog.create_variant slug=%s sku=%s type=%s',
                product.slug, variant.sku, variant.variant_type)
    return _serialize_variant(variant)


@transaction.atomic
def update_variant(*, sku: str, **fields) -> dict:
    """Update an existing variant identified by SKU. Pass any subset
    of fields; only the ones present are touched."""
    from plugins.installed.catalog.models import ProductVariant

    variant = ProductVariant.objects.filter(sku=sku).select_related('product').first()
    if variant is None:
        raise PublishError(f'variant sku {sku!r} not found')
    _apply_variant_fields(variant, fields)
    variant.save()
    return _serialize_variant(variant)
