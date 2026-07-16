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
    # Membership perk: percent off the cart for an active subscriber on this
    # plan (applied at checkout via CART_CALCULATE_BREAKDOWN). 0 = no discount.
    member_discount_percent = models.PositiveSmallIntegerField(
        default=0, help_text='Percent off the cart for active subscribers on this plan (0–100).'
    )
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
    """A customer's active or past subscription to a Plan.

    THE one subscription model (the old ``subscriptions_plus`` plugin shipped
    a second, parallel ``Subscription`` — the PR-#62 class of bug; merged here
    2026-07-16). ``kind`` distinguishes a pure billing subscription ('plan')
    from product-delivery flavours ('replenish' — re-ships every N days;
    'curated' — merchant-rotated box). Delivery subscriptions carry their box
    contents in ``lines`` and their schedule in ``shipments``.
    """

    STATE_CHOICES = [
        ('trialing', 'Trialing'),
        ('active', 'Active'),
        ('past_due', 'Past due'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    KIND_CHOICES = [
        ('plan', 'Plan (billing only)'),
        ('replenish', 'Replenish'),
        ('curated', 'Curated box'),
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
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='plan')
    # Delivery cadence in days for replenish/curated kinds; 0 = ship/bill per
    # the plan's interval.
    cadence_days = models.PositiveIntegerField(default=0)
    next_ship_at = models.DateTimeField(null=True, blank=True, db_index=True)

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


class SubscriptionLine(models.Model):
    """A product in a delivery subscription's box (replenish/curated kinds).

    Absorbed from the deleted ``subscriptions_plus`` plugin (2026-07-16) —
    now FKs THE Subscription instead of a parallel one.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='lines')
    variant = models.ForeignKey(
        'catalog.ProductVariant', on_delete=models.PROTECT, related_name='+'
    )
    quantity = models.PositiveIntegerField(default=1)


class SubscriptionShipment(models.Model):
    """One scheduled (or fulfilled) delivery of a subscription box."""

    STATE_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('prepared', 'Prepared'),
        ('shipped', 'Shipped'),
        ('skipped', 'Skipped'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name='shipments'
    )
    ship_at = models.DateTimeField(db_index=True)
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default='scheduled')
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    class Meta:
        ordering = ['ship_at']


class SubscriptionEvent(models.Model):
    """Audit log of self-serve pause / skip / swap / cancel actions —
    drives the churn-save prompt."""

    KIND_CHOICES = [
        ('created', 'Created'),
        ('paused', 'Paused'),
        ('resumed', 'Resumed'),
        ('skipped', 'Skipped'),
        ('swapped', 'Swapped'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='events')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    at = models.DateTimeField(auto_now_add=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-at']
