"""AliExpress dropshipping — what the platform remembers about the supplier.

* ``AELink`` hangs off a catalog product (and variant): the AliExpress product
  and SKU to order for it (``sku_attr`` is what an order names; "" for a
  single-SKU product), its cost and stock as last read.
* ``AEOrder`` hangs off an order: the AliExpress order(s) it became — one
  store order can become several, one per AliExpress seller — whether they are
  paid, and the tracking as it arrived. The order ships the platform way
  (``plugins.dropshipping.ship_with_tracking``); this is the audit copy.
"""

from __future__ import annotations

import uuid

from morpheus.app import models


class AELink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE, related_name='ae_links'
    )
    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ae_links',
    )
    ae_product_id = models.CharField(max_length=32)
    ae_sku_id = models.CharField(max_length=40, blank=True, help_text='for freight quotes')
    sku_attr = models.CharField(max_length=500, blank=True, help_text='"" for a single-SKU product')
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    stock = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'variant')
        ordering = ['product__name', 'variant__sku']

    def __str__(self) -> str:
        return f'{self.product_id}/{self.variant_id or "-"} → AliExpress {self.ae_product_id} {self.sku_attr}'


class AEOrder(models.Model):
    STATUS_CHOICES = [
        ('sending', 'Being placed on AliExpress'),
        ('placed', 'Placed — pay it in AliExpress'),
        ('paid', 'Paid — the seller is preparing it'),
        ('shipped', 'Shipped (tracking recorded)'),
        ('failed', 'Could not be placed — see the note'),
        ('cancelled', 'Cancelled in Morpheus — cancel it in AliExpress too'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='ae_order')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sending')
    ae_order_ids = models.JSONField(default=list, blank=True)
    ae_status = models.CharField(max_length=40, blank=True, help_text='AliExpress order_status')
    pay_by = models.DateTimeField(
        null=True, blank=True, help_text='AliExpress cancels it unpaid after this'
    )
    tracking_numbers = models.JSONField(
        default=dict, blank=True, help_text='AliExpress order id → tracking'
    )
    carrier = models.CharField(max_length=200, blank=True)
    note = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-sent_at', '-created_at']

    def __str__(self) -> str:
        return f'AliExpress {self.status} for order #{self.order.order_number}'
