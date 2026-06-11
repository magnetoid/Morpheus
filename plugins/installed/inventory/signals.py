from django.db.models.signals import post_save
from django.dispatch import receiver

from core.hooks import MorpheusEvents, hook_registry

from .models import StockLevel


@receiver(post_save, sender=StockLevel)
def stock_level_post_save(sender, instance, created, **kwargs):
    if instance.is_out_of_stock:
        hook_registry.fire(MorpheusEvents.PRODUCT_OUT_OF_STOCK, stock_level=instance)
    elif instance.is_low_stock:
        hook_registry.fire(MorpheusEvents.PRODUCT_LOW_STOCK, stock_level=instance)
