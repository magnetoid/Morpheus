"""Wishlist models — saved items per customer (or session for guests)."""

from __future__ import annotations

import uuid

from django.conf import settings

from morpheus.plugin import models


class Wishlist(models.Model):
    """A wishlist owned by a customer or anonymous session."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='wishlists',
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    name = models.CharField(max_length=120, default='My wishlist')
    is_public = models.BooleanField(default=False)
    share_token = models.CharField(max_length=32, blank=True, unique=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['customer', '-updated_at']),
            models.Index(fields=['session_key', '-updated_at']),
        ]

    def __str__(self) -> str:
        owner = (self.customer.email if self.customer_id else self.session_key) or 'anon'
        return f'Wishlist {self.name} ({owner})'

    @property
    def item_count(self) -> int:
        return self.items.count()


class WishlistItem(models.Model):
    """A saved product (optionally a specific variant) in a wishlist."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='+',
    )
    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='+',
    )
    note = models.CharField(max_length=240, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wishlist', 'product', 'variant')
        ordering = ['-added_at']
