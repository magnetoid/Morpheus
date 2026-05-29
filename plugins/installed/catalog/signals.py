from django.db.models.signals import post_save
from django.dispatch import receiver

from core.hooks import MorpheusEvents, hook_registry

from .models import Category, Collection, Product

# String constant — the event isn't on MorpheusEvents yet; subscribers
# wire to the literal name. Promote to a typed constant once a second
# subscriber appears.
COLLECTION_UPDATED = 'collection.updated'


@receiver(post_save, sender=Product)
def product_post_save(sender, instance, created, **kwargs):
    if created:
        hook_registry.fire(MorpheusEvents.PRODUCT_CREATED, product=instance)
    else:
        hook_registry.fire(MorpheusEvents.PRODUCT_UPDATED, product=instance)


@receiver(post_save, sender=Category)
def category_post_save(sender, instance, created, **kwargs):
    # Skip-if-not-published — SERP pings only make sense for live URLs.
    if not getattr(instance, 'is_active', True):
        return
    hook_registry.fire(MorpheusEvents.CATEGORY_UPDATED, category=instance)


@receiver(post_save, sender=Collection)
def collection_post_save(sender, instance, created, **kwargs):
    if not getattr(instance, 'is_active', True):
        return
    hook_registry.fire(COLLECTION_UPDATED, collection=instance)
