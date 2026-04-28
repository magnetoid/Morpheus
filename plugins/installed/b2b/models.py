"""B2B models — quotes, net terms, per-account price lists.

Reuses the `crm.Account` model (which already exists). Quotes are a
distinct lifecycle: customer or sales rep proposes pricing, customer
accepts, system converts to an Order with locked prices.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from morpheus import models
from djmoney.models.fields import MoneyField


class PriceList(models.Model):
    """A named price list, optionally pinned to one or more Accounts."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    accounts = models.ManyToManyField(
        'crm.Account', blank=True, related_name='price_lists',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', 'name']

    def __str__(self) -> str:
        return self.name


class PriceListItem(models.Model):
    """Override price for a product/variant under a price list."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE)
    variant = models.ForeignKey(
        'catalog.ProductVariant', on_delete=models.CASCADE,
        null=True, blank=True,
    )
    price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')

    class Meta:
        unique_together = ('price_list', 'product', 'variant')


class Quote(models.Model):
    """A negotiated proposal — line items at agreed prices."""

    STATE_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('viewed', 'Viewed'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('converted', 'Converted to order'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote_number = models.CharField(max_length=24, unique=True, blank=True)
    account = models.ForeignKey(
        'crm.Account', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='quotes',
    )
    contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='received_quotes',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='owned_quotes',
    )
    state = models.CharField(max_length=12, choices=STATE_CHOICES, default='draft', db_index=True)

    subtotal = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    discount_total = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    tax_total = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    total = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)

    valid_until = models.DateField(null=True, blank=True)
    note_to_customer = models.TextField(blank=True)
    internal_note = models.TextField(blank=True)

    converted_order = models.ForeignKey(
        'orders.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='source_quote',
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', '-created_at']),
            models.Index(fields=['state', '-created_at']),
        ]

    def __str__(self) -> str:
        return self.quote_number or f'Quote {self.id}'

    def save(self, *args, **kwargs):
        if not self.quote_number:
            from django.utils import timezone
            self.quote_number = f'Q-{timezone.now().strftime("%y%m%d")}{str(self.id)[:6].upper()}'
        super().save(*args, **kwargs)


class QuoteLine(models.Model):
    """A line item on a Quote."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.SET_NULL, null=True, blank=True,
    )
    variant = models.ForeignKey(
        'catalog.ProductVariant', on_delete=models.SET_NULL, null=True, blank=True,
    )
    description = models.CharField(max_length=240)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    line_total = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')


class NetTermsAgreement(models.Model):
    """Agreement that an Account can pay invoices on net-N terms."""

    NET_DAYS_CHOICES = [
        (15, 'Net 15'),
        (30, 'Net 30'),
        (45, 'Net 45'),
        (60, 'Net 60'),
        (90, 'Net 90'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.OneToOneField(
        'crm.Account', on_delete=models.CASCADE, related_name='net_terms',
    )
    net_days = models.PositiveSmallIntegerField(choices=NET_DAYS_CHOICES, default=30)
    credit_limit = MoneyField(
        max_digits=14, decimal_places=2, default_currency='USD',
        null=True, blank=True,
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
