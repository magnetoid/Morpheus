"""Zendrop dropshipping — what the platform remembers about the supplier.

Two extensions of models that already exist, never a parallel copy:

* ``ZendropLink`` hangs off a catalog product (and variant): which Zendrop
  product and variant to order for it.
* ``ZendropOrder`` hangs off an order: that it was placed in Zendrop (when, and
  Zendrop's order number) and the tracking as it arrived. The tracking that
  *ships* the order lives where the platform owns it — ``Order.ship()`` and an
  ``orders.Fulfillment`` row; this is the audit copy for the Zendrop page.
"""

from __future__ import annotations

import uuid

from morpheus.app import models


class ZendropLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE, related_name='zendrop_links'
    )
    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='zendrop_links',
    )
    zendrop_product_id = models.CharField(max_length=64, blank=True)
    zendrop_variant_id = models.CharField(max_length=64, blank=True)
    product_url = models.URLField(max_length=500, blank=True, help_text='Zendrop product page')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'variant')
        ordering = ['product__name', 'variant__sku']

    def __str__(self) -> str:
        return f'{self.store_sku} → Zendrop {self.zendrop_product_id or "?"}/{self.zendrop_variant_id or "-"}'

    @property
    def store_sku(self) -> str:
        return self.variant.sku if self.variant_id else self.product.sku


class ZendropOrder(models.Model):
    STATUS_CHOICES = [
        ('placed', 'Placed in Zendrop'),
        ('shipped', 'Shipped (tracking recorded)'),
        ('cancelled', 'Cancelled after placing — cancel in Zendrop too'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        'orders.Order', on_delete=models.CASCADE, related_name='zendrop_order'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='placed')
    zendrop_order_number = models.CharField(max_length=100, blank=True)
    placed_at = models.DateTimeField(null=True, blank=True)
    tracking_number = models.CharField(max_length=200, blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-placed_at', '-created_at']

    def __str__(self) -> str:
        return f'Zendrop {self.status} for order #{self.order.order_number}'
