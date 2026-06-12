"""Subscriptions Plus: subscription, schedule, churn-save log.

`Subscription` is the contract — the customer opted into recurring
orders. `SubscriptionShipment` is the schedule row (one per future
ship date). `SubscriptionEvent` is the audit log of pauses / skips /
swaps / cancels (used to drive the churn-save prompt).
"""
from __future__ import annotations

from morpheus import models


class Subscription(models.Model):
    STATE_CHOICES = (
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
    )
    FLAVOUR_CHOICES = (('replenish', 'Replenish'), ('curated', 'Curated'))

    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='+')
    flavour = models.CharField(max_length=10, choices=FLAVOUR_CHOICES, default='replenish')
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default='active')
    cadence_days = models.PositiveIntegerField(default=30)
    next_ship_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['state', 'next_ship_at'])]


class SubscriptionLine(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='lines')
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.PROTECT, related_name='+')
    quantity = models.PositiveIntegerField(default=1)


class SubscriptionShipment(models.Model):
    STATE_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('prepared', 'Prepared'),
        ('shipped', 'Shipped'),
        ('skipped', 'Skipped'),
    )
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='shipments')
    ship_at = models.DateTimeField(db_index=True)
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default='scheduled')
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )

    class Meta:
        ordering = ['ship_at']


class SubscriptionEvent(models.Model):
    KIND_CHOICES = (
        ('created', 'Created'),
        ('paused', 'Paused'),
        ('resumed', 'Resumed'),
        ('skipped', 'Skipped'),
        ('swapped', 'Swapped'),
        ('cancelled', 'Cancelled'),
    )
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='events')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    at = models.DateTimeField(auto_now_add=True)
    meta_json = models.TextField(default='{}', blank=True)
