"""
Affiliate platform — links, attribution, conversions, payouts.

Domain:

    Affiliate                 — a partner promoting the store (per merchant)
    AffiliateProgram          — commission rules
    AffiliateLink             — per-affiliate trackable URL
    AffiliateClick            — recorded click (anonymous; cookie-set on storefront)
    AffiliateConversion       — order tied to an affiliate via attribution window
    AffiliatePayout           — periodic payout of accrued commissions
"""
from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from morpheus import models
from djmoney.models.fields import MoneyField


class AffiliateProgram(models.Model):
    """Commission terms a merchant offers to affiliates."""

    COMMISSION_TYPE_CHOICES = [
        ('percent', 'Percent of order'),
        ('fixed', 'Fixed amount per conversion'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    commission_type = models.CharField(max_length=10, choices=COMMISSION_TYPE_CHOICES, default='percent')
    commission_value = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        help_text='Percent (0-100) for percent type, or amount for fixed type.',
    )
    cookie_window_days = models.PositiveSmallIntegerField(default=30)
    minimum_payout = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=50)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class Affiliate(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('suspended', 'Suspended'),
        ('rejected', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program = models.ForeignKey(AffiliateProgram, on_delete=models.CASCADE, related_name='affiliates')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='affiliate_accounts',
    )
    handle = models.SlugField(max_length=80, unique=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending', db_index=True)
    company = models.CharField(max_length=200, blank=True)
    payout_email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    accrued_balance = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    lifetime_paid = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('program', 'user')
        indexes = [
            models.Index(fields=['program', 'status']),
        ]

    def __str__(self) -> str:
        return f'{self.handle} ({self.status})'


class AffiliateLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='links')
    code = models.CharField(max_length=24, unique=True, db_index=True)
    landing_url = models.CharField(max_length=500, default='/')
    label = models.CharField(max_length=100, blank=True)
    # 2026 affiliate-app standard: attribute conversions when this
    # promo code is redeemed at checkout, no click required. Used for
    # influencer / podcast / out-of-band collaborations.
    coupon_code = models.CharField(
        max_length=40, blank=True, db_index=True,
        help_text=(
            'Optional: if set, redeeming this coupon code at checkout '
            'attributes the order to this affiliate without needing a '
            'referral click.'
        ),
    )
    is_active = models.BooleanField(default=True, db_index=True)
    click_count = models.PositiveIntegerField(default=0)
    conversion_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = secrets.token_urlsafe(8)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f'/r/{self.code}'


class AffiliateClick(models.Model):
    """Anonymous click record. PII is intentionally minimal."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    link = models.ForeignKey(AffiliateLink, on_delete=models.CASCADE, related_name='clicks')
    referer = models.CharField(max_length=500, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True, db_index=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-occurred_at']


class AffiliateConversion(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='conversions')
    link = models.ForeignKey(AffiliateLink, on_delete=models.SET_NULL, null=True, blank=True)
    order = models.OneToOneField(
        'orders.Order', on_delete=models.CASCADE, related_name='affiliate_conversion',
    )
    commission = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['affiliate', 'status']),
        ]


class AffiliatePayout(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='payouts')
    amount = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    method = models.CharField(max_length=40, blank=True)
    external_reference = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']
