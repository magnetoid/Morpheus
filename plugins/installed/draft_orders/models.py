"""Draft orders — quote/invoice flow.

A staff-built order that can be priced, shared with the customer, and
later converted to a real Order when payment is collected. Lives
separately from the FSM-managed `orders.Order` so it doesn't have to
fight the protected state machine.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from morpheus import models
from djmoney.models.fields import MoneyField


class DraftOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent to customer'),
        ('accepted', 'Accepted'),
        ('converted', 'Converted to order'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.CharField(max_length=24, unique=True, editable=False)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='draft')

    customer = models.ForeignKey(
        'customers.Customer', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='draft_orders',
    )
    customer_email = models.EmailField(blank=True)

    channel = models.ForeignKey(
        'core.StoreChannel', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='draft_orders',
    )

    subtotal = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    discount_total = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    tax_total = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    shipping_total = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    total = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)

    shipping_address = models.JSONField(default=dict, blank=True)
    billing_address = models.JSONField(default=dict, blank=True)

    note = models.TextField(blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='draft_orders_created',
    )
    converted_order_id = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Draft #{self.number}'

    def save(self, *args, **kwargs):
        if not self.number:
            import random, string
            self.number = 'DR' + ''.join(random.choices(string.digits, k=8))
        super().save(*args, **kwargs)


class DraftOrderLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    draft = models.ForeignKey(DraftOrder, on_delete=models.CASCADE, related_name='lines')
    variant = models.ForeignKey(
        'catalog.ProductVariant', on_delete=models.PROTECT,
        null=True, blank=True, related_name='+',
    )
    product_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, blank=True)
    unit_price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['id']

    @property
    def line_total(self):
        return self.unit_price * self.quantity
