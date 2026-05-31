"""Loyalty-points ledger.

A single ``PointsTransaction`` table — every earn / spend / adjustment is a
row. Balance = sum of points for that customer. No materialised wallet
field; the catalog is small enough that the SUM is cheap and we never have
to worry about drift.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class PointsTransaction(models.Model):
    REASON_CHOICES = [
        ('earn_order', 'Earned on order'),
        ('spend_order', 'Redeemed on order'),
        ('adjust', 'Manual adjustment'),
        ('expire', 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='points_transactions',
    )
    points = models.IntegerField(help_text='Positive = earn, negative = spend.')
    reason = models.CharField(max_length=16, choices=REASON_CHOICES, default='earn_order')
    order_number = models.CharField(max_length=40, blank=True, default='')
    note = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['customer', '-created_at'])]

    def __str__(self) -> str:
        sign = '+' if self.points >= 0 else ''
        return f'{sign}{self.points} ({self.reason}) → {self.customer_id}'


# ---------------------------------------------------------------------------
# Tiered status (Bronze/Silver/Gold), referral tracking, RFM segments
# Added v1.1.0 — sprint priority #13. Loyalty is no longer just points;
# it's tier-driven status + referral-attributed acquisition + RFM-based
# segmentation feeding email + storefront personalisation.
# ---------------------------------------------------------------------------


class LoyaltyTier(models.Model):
    """A status tier with a 12-month-revenue threshold + perks.

    Tier assignment is computed nightly from the customer's last 12
    months of order revenue (see services_tiers.assign_tiers). Tiers
    are merchant-configurable — defaults: Bronze 0, Silver 500, Gold 2000.
    """

    key = models.SlugField(max_length=32, unique=True)
    label = models.CharField(max_length=64)
    min_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Trailing 12-month revenue threshold (in shop currency)',
    )
    rank = models.PositiveSmallIntegerField(
        help_text='Higher = better tier; used to sort + compare'
    )
    perks = models.JSONField(
        default=dict,
        blank=True,
        help_text='{free_shipping_above, points_multiplier, early_access}',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'loyalty_tier'
        ordering = ['rank']

    def __str__(self) -> str:
        return f'{self.label} (rank {self.rank})'


class CustomerTier(models.Model):
    """Current tier per customer — denormalised for fast PDP/cart lookups."""

    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='loyalty_tier',
    )
    tier = models.ForeignKey(LoyaltyTier, on_delete=models.SET_NULL, null=True, blank=True)
    revenue_12m = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Cached trailing 12-month revenue for this customer',
    )
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'loyalty_customer_tier'

    def __str__(self) -> str:
        return f'{self.customer_id} → {self.tier_id}'


REFERRAL_STATUS = (
    ('pending', 'Pending'),
    ('qualified', 'Qualified'),
    ('rewarded', 'Rewarded'),
    ('expired', 'Expired'),
)


class Referral(models.Model):
    """One row per (referrer, referee) pair.

    Flow: referrer shares their code; referee signs up via the code →
    `Referral.pending` row created. Referee places their first order →
    transition to `qualified`. On qualification we mint a points
    transaction for each side (referrer reward + referee discount) and
    transition to `rewarded`.
    """

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referrals_made',
    )
    referee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='referrals_received',
    )
    code = models.CharField(max_length=32, db_index=True)
    status = models.CharField(
        max_length=16, choices=REFERRAL_STATUS, default='pending', db_index=True
    )
    qualifying_order_number = models.CharField(max_length=40, blank=True, default='')
    referrer_reward_points = models.PositiveIntegerField(default=0)
    referee_reward_points = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    qualified_at = models.DateTimeField(null=True, blank=True)
    rewarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'loyalty_referral'
        constraints = [
            models.UniqueConstraint(
                fields=['referrer', 'referee'], name='loyalty_referral_unique_pair'
            ),
        ]
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.referrer_id} → {self.referee_id} ({self.status})'


class CustomerRFM(models.Model):
    """Recency / Frequency / Monetary score per customer.

    Each axis is bucketed 1-5 (5 = best) using quintile splits over the
    customer base. The composite segment key is the concatenation
    (e.g. '555' = champion, '111' = lost). Used by email automation +
    storefront personalisation to target the right offer to the right
    cohort.
    """

    SEGMENTS = (
        ('champion', 'Champion'),
        ('loyal', 'Loyal customer'),
        ('promising', 'Promising'),
        ('at_risk', 'At risk'),
        ('hibernating', 'Hibernating'),
        ('lost', 'Lost'),
        ('new', 'New customer'),
    )

    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rfm',
    )
    r_score = models.PositiveSmallIntegerField(help_text='1-5; 5=most recent')
    f_score = models.PositiveSmallIntegerField(help_text='1-5; 5=most frequent')
    m_score = models.PositiveSmallIntegerField(help_text='1-5; 5=biggest spender')
    composite = models.CharField(max_length=3, db_index=True)
    segment = models.CharField(max_length=16, choices=SEGMENTS, db_index=True)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'loyalty_customer_rfm'

    def __str__(self) -> str:
        return f'{self.customer_id}:{self.composite}/{self.segment}'
