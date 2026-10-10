"""CJdropshipping — what the platform remembers about the supplier.

Two extensions of models that already exist, never a parallel copy:

* ``CJLink`` hangs off a catalog product (and variant): which CJ variant to
  order for it, what it costs at CJ, and how much CJ has in stock.
* ``CJOrder`` hangs off an order: the CJ order it became, whether it is paid,
  and the tracking as it arrived. The tracking that *ships* the order lives
  where the platform owns it — ``Order.ship()`` and an ``orders.Fulfillment``
  row (``plugins.dropshipping.ship_with_tracking``); this is the audit copy.
"""

from __future__ import annotations

import uuid

from morpheus.app import models


class CJLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE, related_name='cj_links'
    )
    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cj_links',
    )
    cj_product_id = models.CharField(max_length=64, blank=True, help_text='CJ pid')
    cj_variant_id = models.CharField(max_length=64, help_text='CJ vid — what an order names')
    cj_sku = models.CharField(max_length=100, blank=True)
    cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, help_text='USD'
    )
    stock = models.IntegerField(null=True, blank=True, help_text='CJ stock, all warehouses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'variant')
        ordering = ['product__name', 'variant__sku']

    def __str__(self) -> str:
        return f'{self.product_id}/{self.variant_id or "-"} → CJ {self.cj_variant_id}'


class CJOrder(models.Model):
    STATUS_CHOICES = [
        ('sending', 'Being sent to CJ'),
        ('created', 'Created in CJ — awaiting payment'),
        ('paid', 'Paid — CJ is preparing it'),
        ('shipped', 'Shipped (tracking recorded)'),
        ('failed', 'Could not be sent — see the note'),
        ('cancelled', 'Cancelled in Morpheus — cancel in CJ too'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='cj_order')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sending')
    cj_order_id = models.CharField(max_length=64, blank=True, db_index=True)
    cj_status = models.CharField(max_length=40, blank=True, help_text='CJ orderStatus')
    logistic_name = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, help_text='USD'
    )
    tracking_number = models.CharField(max_length=200, blank=True)
    carrier = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-sent_at', '-created_at']

    def __str__(self) -> str:
        return f'CJ {self.status} for order #{self.order.order_number}'
