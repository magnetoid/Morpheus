"""Promotion engine v2 — rule-based discounts.

A `Promotion` is a named campaign scoped to one or more channels with a
validity window. It owns one or more `PromotionRule` rows; each rule has
JSON predicates (when does this fire?) and a JSON action (what happens
when it fires? — % off, fixed off, free shipping, gift product).

This is decoupled from `marketing.Coupon` (which is a flat code-based
coupon). Coupons may unlock specific promotions in the future, but the
engine itself doesn't require a code.
"""
from __future__ import annotations

import uuid

from morpheus import models


class Promotion(models.Model):
    TYPE_CATALOG = 'catalog'
    TYPE_ORDER = 'order'
    TYPES = [
        (TYPE_CATALOG, 'Catalog (line-level)'),
        (TYPE_ORDER, 'Order (whole-cart)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=16, choices=TYPES, default=TYPE_ORDER)

    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=100, help_text='Lower runs first.')

    channels = models.JSONField(default=list, blank=True, help_text='Channel slugs; empty = all channels.')
    requires_coupon = models.CharField(max_length=64, blank=True, help_text='Optional coupon code that unlocks this promotion.')

    times_used = models.PositiveIntegerField(default=0)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', '-created_at']

    def __str__(self) -> str:
        return self.name


class PromotionRule(models.Model):
    """A predicate + action pair owned by a Promotion."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='rules')
    label = models.CharField(max_length=200, blank=True)

    # Predicates — all must match. Recognised keys handled by services.evaluate:
    #   min_subtotal: number
    #   max_subtotal: number
    #   currencies: [str]
    #   countries: [str]
    #   customer_groups: [str]
    #   product_ids: [str]
    #   category_slugs: [str]
    #   first_order: bool
    predicates = models.JSONField(default=dict, blank=True)

    # Action — exactly one shape. Recognised:
    #   {"kind": "percent_off", "value": 10}
    #   {"kind": "fixed_off", "value": 5, "currency": "USD"}
    #   {"kind": "free_shipping"}
    #   {"kind": "gift", "product_id": "..."}
    action = models.JSONField(default=dict)

    class Meta:
        ordering = ['promotion__priority', 'id']

    def __str__(self) -> str:
        return f'{self.promotion.name} → {self.action.get("kind", "?")}'


class PromotionApplication(models.Model):
    """Audit trail — which order got which promotion, for how much."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.ForeignKey(Promotion, on_delete=models.PROTECT, related_name='applications')
    rule = models.ForeignKey(PromotionRule, on_delete=models.SET_NULL, null=True, blank=True)
    order_id = models.CharField(max_length=64, blank=True)
    customer_id = models.CharField(max_length=64, blank=True)
    discount_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default='USD')
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-applied_at']
