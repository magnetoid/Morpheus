"""DSers dropshipping — what the platform needs to remember about a supplier.

Two extensions of models that already exist, never a parallel copy:

* ``SupplierLink`` hangs off a catalog product (and variant): which AliExpress
  item and SKU DSers should order for it. This is what the `import_products`
  mapping file is built from.
* ``OrderSync`` hangs off an order: that it was handed to DSers (when, in which
  export), the AliExpress order number DSers reported back, and the tracking
  number as it arrived. The tracking that *ships* the order lives where the
  platform owns it — ``Order.tracking_number`` / ``Order.ship()`` and an
  ``orders.Fulfillment`` row — this is the audit copy for the DSers page.
"""

from __future__ import annotations

import uuid

from morpheus.app import models


class SupplierLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE, related_name='dsers_links'
    )
    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='dsers_links',
    )
    supplier_url = models.URLField(max_length=500, blank=True, help_text='AliExpress product URL')
    supplier_sku = models.CharField(
        max_length=200, blank=True, help_text="The supplier's SKU/variant id as DSers shows it"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'variant')
        ordering = ['product__name', 'variant__sku']

    def __str__(self) -> str:
        return f'{self.store_sku} → {self.supplier_url or "(no supplier)"}'

    @property
    def store_sku(self) -> str:
        return self.variant.sku if self.variant_id else self.product.sku


class OrderSync(models.Model):
    STATUS_CHOICES = [
        ('exported', 'Exported to DSers'),
        ('shipped', 'Shipped (tracking imported)'),
        ('cancelled', 'Cancelled after export — cancel in DSers too'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        'orders.Order', on_delete=models.CASCADE, related_name='dsers_sync'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='exported')
    batch_id = models.UUIDField(null=True, blank=True)
    exported_at = models.DateTimeField(null=True, blank=True)
    supplier_order_number = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=200, blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-exported_at', '-created_at']

    def __str__(self) -> str:
        return f'DSers {self.status} for order #{self.order.order_number}'
