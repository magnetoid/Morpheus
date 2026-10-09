"""Auto-regenerate the WebStory whenever a Product or its images change.

Three receivers, all fail-soft:

  * Product.post_save  → ensure_story(product) on any active product
    that has at least one image.
  * ProductImage.post_save  → ensure_story(image.product) so a new
    cover image immediately reshuffles the story without waiting for
    the merchant to re-save the product.
  * ProductImage.post_delete  → the same, after the commit, and only while
    the product still exists and is active: deleting a product deletes its
    images first, and a story built during that delete broke it.

Failures only log; we never want a story-build crash to block a
product save. Each build runs in its own savepoint: on Postgres a query that
fails inside the caller's transaction aborts it even when the error is caught,
and the rest of the caller's save then raises. Rolling back to the savepoint
confines a failed story to the story.
"""

from __future__ import annotations

import logging

from django.db import transaction
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

        with transaction.atomic():
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

        with transaction.atomic():
            ensure_story(product)
    except Exception:  # noqa: BLE001
        logger.warning('webstories: ensure_story-on-image(%s) failed', product.pk, exc_info=True)


@receiver(post_delete, sender='catalog.ProductImage')
def _regenerate_on_image_delete(sender, instance, **kwargs):  # noqa: ARG001
    product_id = getattr(instance, 'product_id', None)
    if product_id is None:
        return
    # Deleting a product deletes its images first. A story rebuilt right here
    # would point at a product that is gone by commit, and Postgres then rejects
    # the whole delete on the deferred foreign key (beta.irvingsurvival.com,
    # 2026-10-09). Rebuild after the commit, for a product still on sale.
    transaction.on_commit(lambda: _rebuild_after_image_delete(product_id))


def _live_product(product_id):
    """The product, if it still exists and is on sale."""
    from django.apps import apps  # noqa: PLC0415

    product_model = apps.get_model('catalog', 'Product')
    return product_model.objects.filter(pk=product_id, status='active').first()


def _rebuild_after_image_delete(product_id) -> None:
    try:
        product = _live_product(product_id)
        if product is None:
            return
        from plugins.installed.webstories.services import ensure_story  # noqa: PLC0415

        with transaction.atomic():
            ensure_story(product)
    except Exception:  # noqa: BLE001
        logger.warning(
            'webstories: ensure_story-on-img-delete(%s) failed', product_id, exc_info=True
        )
