"""Save-for-later: a cart-move list + price snapshots.

A `SavedItem` is an entry in a customer's "save for later" list.
A `PriceSnapshot` is the price at the time the item was saved —
we compare on each tick to decide whether to queue a notification.
"""
from __future__ import annotations

from morpheus import models


class SavedItem(models.Model):
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='+')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='+')
    moved_at = models.DateTimeField(auto_now_add=True)
    # The snapshot price is the price at the time the item was moved
    # to the saved list. We compare on every price-drop tick.
    snapshotted_price_cents = models.PositiveIntegerField(default=0)
    snapshotted_in_stock = models.BooleanField(default=True)

    class Meta:
        unique_together = ('customer', 'product')
        ordering = ['-moved_at']


class PriceSnapshot(models.Model):
    """Periodic snapshot of a product's price for change detection."""

    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='+')
    price_cents = models.PositiveIntegerField(default=0)
    in_stock = models.BooleanField(default=True)
    observed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['product', '-observed_at'])]
        ordering = ['-observed_at']


class SharedWishlist(models.Model):
    """A shareable, read-only link to a customer's wishlist."""

    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='+')
    token = models.SlugField(max_length=64, unique=True, db_index=True)
    title = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
