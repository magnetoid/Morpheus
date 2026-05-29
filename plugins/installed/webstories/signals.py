"""Auto-regenerate the WebStory whenever a Product or its images change.

Two receivers, both fail-soft:

  * Product.post_save  → ensure_story(product) on any active product
    that has at least one image.
  * ProductImage.post_save  → ensure_story(image.product) so a new
    cover image immediately reshuffles the story without waiting for
    the merchant to re-save the product.

Failures only log; we never want a story-build crash to block a
product save.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger('morpheus.webstories')


@receiver(post_save, sender='catalog.Product')
def _regenerate_on_product_save(sender, instance, created, **kwargs):  # noqa: ARG001
    if getattr(instance, 'status', '') != 'active':
        return
    try:
        if not instance.images.exists():
            return
        from plugins.installed.webstories.services import ensure_story  # noqa: PLC0415

        ensure_story(instance)
    except Exception:  # noqa: BLE001
        logger.warning('webstories: ensure_story(%s) failed', instance.pk, exc_info=True)


@receiver(post_save, sender='catalog.ProductImage')
def _regenerate_on_image_save(sender, instance, created, **kwargs):  # noqa: ARG001
    product = getattr(instance, 'product', None)
    if product is None or getattr(product, 'status', '') != 'active':
        return
    try:
        from plugins.installed.webstories.services import ensure_story  # noqa: PLC0415

        ensure_story(product)
    except Exception:  # noqa: BLE001
        logger.warning('webstories: ensure_story-on-image(%s) failed', product.pk, exc_info=True)


@receiver(post_delete, sender='catalog.ProductImage')
def _regenerate_on_image_delete(sender, instance, **kwargs):  # noqa: ARG001
    product = getattr(instance, 'product', None)
    if product is None:
        return
    try:
        from plugins.installed.webstories.services import ensure_story  # noqa: PLC0415

        ensure_story(product)
    except Exception:  # noqa: BLE001
        logger.warning(
            'webstories: ensure_story-on-img-delete(%s) failed', product.pk, exc_info=True
        )
