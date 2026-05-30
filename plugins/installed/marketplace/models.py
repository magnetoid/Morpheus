"""
Multivendor marketplace.

The catalog plugin already ships a `Vendor` model. This plugin layers
marketplace concerns on top: vendor onboarding (`VendorApplication`),
splitting an order into per-vendor sub-orders (`VendorOrder`), and
periodic vendor payouts (`VendorPayout`).

Design choices
--------------
* We do NOT replace `catalog.Vendor`; we extend it via FK so existing data
  keeps working.
* Splitting an order into `VendorOrder` rows happens on `order.placed`. Each
  VendorOrder records the vendor's gross + commission + net amount. This is
  the single source of truth for accounting.
* Payouts are explicit transactions (`VendorPayout`) — never auto-deducted.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from djmoney.models.fields import MoneyField

from morpheus import models


class VendorApplication(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('reviewing', 'Reviewing'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vendor_applications',
    )
    business_name = models.CharField(max_length=200)
    contact_email = models.EmailField()
    description = models.TextField(blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    payout_method = models.CharField(max_length=40, blank=True)
    documents = models.JSONField(default=list)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='submitted', db_index=True
    )
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)


class VendorPayoutAccount(models.Model):
    """Banking / payout details linked to a catalog.Vendor."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.OneToOneField(
        'catalog.Vendor',
        on_delete=models.CASCADE,
        related_name='payout_account',
    )
    method = models.CharField(max_length=40)
    external_account = models.CharField(max_length=200, blank=True)
    accrued_balance = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    lifetime_paid = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)


class VendorOrder(models.Model):
    """Per-vendor slice of a customer order."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent_order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='vendor_orders',
    )
    vendor = models.ForeignKey(
        'catalog.Vendor',
        on_delete=models.PROTECT,
        related_name='vendor_orders',
    )
    gross = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    commission = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    net = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default='pending', db_index=True
    )
    items_snapshot = models.JSONField(default=list)
    tracking_number = models.CharField(max_length=200, blank=True)
    tracking_url = models.URLField(max_length=500, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('parent_order', 'vendor')
        indexes = [
            models.Index(fields=['vendor', 'status']),
        ]


class VendorPayout(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(
        'catalog.Vendor',
        on_delete=models.PROTECT,
        related_name='payouts',
    )
    amount = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True
    )
    method = models.CharField(max_length=40, blank=True)
    external_reference = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']
