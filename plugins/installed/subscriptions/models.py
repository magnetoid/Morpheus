"""Subscription models — plans, customer subscriptions, invoices.

Stripe-integration is left as a separate adapter module so the plugin
runs end-to-end with `provider='manual'` (admin-managed billing) on day
one. Switch `Plan.provider='stripe'` when ready.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from djmoney.models.fields import MoneyField

from morpheus import models


class Plan(models.Model):
    """A pricing plan a customer can subscribe to."""

    INTERVAL_CHOICES = [
        ('day', 'Daily'),
        ('week', 'Weekly'),
        ('month', 'Monthly'),
        ('year', 'Yearly'),
    ]
    PROVIDER_CHOICES = [
        ('manual', 'Manual / admin'),
        ('stripe', 'Stripe Billing'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    price = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    interval = models.CharField(max_length=10, choices=INTERVAL_CHOICES, default='month')
    interval_count = models.PositiveSmallIntegerField(default=1)
    trial_days = models.PositiveSmallIntegerField(default=0)
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES, default='manual')
    provider_price_id = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return f'{self.name} ({self.price}/{self.interval})'


class Subscription(models.Model):
    """A customer's active or past subscription to a Plan."""

    STATE_CHOICES = [
        ('trialing', 'Trialing'),
        ('active', 'Active'),
        ('past_due', 'Past due'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions',
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    state = models.CharField(
        max_length=10, choices=STATE_CHOICES, default='trialing', db_index=True
    )

    started_at = models.DateTimeField(auto_now_add=True)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True, db_index=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    provider_subscription_id = models.CharField(max_length=200, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['customer', 'state']),
            models.Index(fields=['state', 'current_period_end']),
        ]


class SubscriptionInvoice(models.Model):
    """One billing cycle's invoice."""

    STATE_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('paid', 'Paid'),
        ('void', 'Void'),
        ('uncollectible', 'Uncollectible'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name='invoices'
    )
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    amount = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    state = models.CharField(max_length=14, choices=STATE_CHOICES, default='open', db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    provider_invoice_id = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-period_start']
        indexes = [
            models.Index(fields=['subscription', '-period_start']),
            models.Index(fields=['state', 'period_end']),
        ]
