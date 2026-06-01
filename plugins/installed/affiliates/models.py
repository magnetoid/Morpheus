"""
Affiliate platform — links, attribution, conversions, payouts.

Domain:

    Affiliate                 — a partner promoting the store (per merchant)
    AffiliateProgram          — commission rules (tiers, per-category override,
                                auto-approve threshold)
    AffiliateLink             — per-affiliate trackable URL
    AffiliateClick            — recorded click (anonymous; cookie-set on storefront)
    AffiliateConversion       — order tied to an affiliate via attribution window
    AffiliatePayout           — periodic payout of accrued commissions
    AffiliateWidget           — embeddable shop widget (iframe + JS snippet) owned
                                by an affiliate; renders public product cards that
                                link through the affiliate's ref code
"""

from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from djmoney.models.fields import MoneyField

from morpheus import models


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
    commission_type = models.CharField(
        max_length=10, choices=COMMISSION_TYPE_CHOICES, default='percent'
    )
    commission_value = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        help_text='Percent (0-100) for percent type, or amount for fixed type.',
    )
    cookie_window_days = models.PositiveSmallIntegerField(default=30)
    minimum_payout = MoneyField(max_digits=14, decimal_places=2, default_currency='USD', default=50)
    is_active = models.BooleanField(default=True, db_index=True)

    # ── OPTIONS (A) ──────────────────────────────────────────────────────
    # Commission tiers: a graduated percent schedule keyed off the
    # affiliate's lifetime approved-conversion count. Stored as an ordered
    # list of {"name", "min_conversions", "percent"} dicts, e.g.:
    #   [{"name": "Bronze", "min_conversions": 0,  "percent": 10},
    #    {"name": "Silver", "min_conversions": 10, "percent": 15},
    #    {"name": "Gold",   "min_conversions": 50, "percent": 20}]
    # The effective tier is the highest `min_conversions` the affiliate has
    # reached. Empty list ⇒ flat `commission_value` (back-compat default).
    # Only meaningful for commission_type='percent'.
    tiers = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            'Optional graduated commission schedule (percent type only). '
            'List of {name, min_conversions, percent} ordered by threshold.'
        ),
    )
    # Per-category commission override: {category_slug: percent}. When an
    # order line's product belongs to one of these categories, that line
    # earns the override percent instead of the tier/base percent. Empty
    # dict ⇒ no overrides. Percent type only.
    category_commission_overrides = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            'Optional {category_slug: percent} map. Order lines whose product '
            'is in a listed category earn that percent instead of the base/tier rate.'
        ),
    )
    # Auto-approve a pending affiliate once they reach this many attributed
    # conversions (counting pending too — the signal is "they can sell").
    # 0 ⇒ disabled (manual approval only).
    auto_approve_after = models.PositiveSmallIntegerField(
        default=0,
        help_text=(
            'Auto-approve a pending affiliate after this many attributed '
            'conversions. 0 disables auto-approval (manual only).'
        ),
    )

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
    program = models.ForeignKey(
        AffiliateProgram, on_delete=models.CASCADE, related_name='affiliates'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='affiliate_accounts',
    )
    handle = models.SlugField(max_length=80, unique=True)
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default='pending', db_index=True
    )
    display_name = models.CharField(max_length=200, blank=True)
    company = models.CharField(max_length=200, blank=True)
    payout_email = models.EmailField(blank=True)
    PAYOUT_METHOD_CHOICES = [
        ('paypal', 'PayPal'),
        ('wire', 'Bank wire'),
        ('credit', 'Store credit (+10%)'),
    ]
    preferred_payout_method = models.CharField(
        max_length=12,
        choices=PAYOUT_METHOD_CHOICES,
        default='paypal',
        blank=True,
    )
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
        max_length=40,
        blank=True,
        db_index=True,
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
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='affiliate_conversion',
    )
    commission = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True
    )
    locked_until = models.DateTimeField(null=True, blank=True)
    payout = models.ForeignKey(
        'AffiliatePayout',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bundled_conversions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['affiliate', 'status']),
        ]


class AffiliateWidget(models.Model):
    """An embeddable shop widget owned by an affiliate.

    Renders a small, themed grid of *public* product cards on an external
    site (via iframe or JS snippet). Every card links to the storefront
    product through the affiliate's ``/r/<code>`` redirect, so a click
    attributes through the existing ``record_click`` + cookie path.

    Security note: this object is addressed PUBLICLY and cross-origin by an
    unguessable ``key``. It must never expose anything beyond public product
    data + the affiliate's ref code. No customer/order/PII fields here.
    """

    SOURCE_CHOICES = [
        ('featured', 'Featured products'),
        ('category', 'A category'),
        ('products', 'Specific products'),
    ]
    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'Auto (match visitor)'),
    ]
    LAYOUT_CHOICES = [
        ('grid', 'Grid'),
        ('carousel', 'Carousel'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='widgets')
    # The tracked link whose code is appended to every product URL. Optional:
    # when unset we fall back to the affiliate's oldest active link at render
    # time. SET_NULL so deleting a link doesn't delete the widget.
    link = models.ForeignKey(
        AffiliateLink,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='widgets',
    )
    title = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES, default='featured')
    # When source='category': the category slug to pull from.
    category_slug = models.SlugField(max_length=200, blank=True)
    # When source='products': explicit product UUIDs (order preserved on render).
    product_ids = models.JSONField(default=list, blank=True)
    limit = models.PositiveSmallIntegerField(default=6)
    theme = models.CharField(max_length=8, choices=THEME_CHOICES, default='auto')
    layout = models.CharField(max_length=8, choices=LAYOUT_CHOICES, default='grid')
    is_active = models.BooleanField(default=True, db_index=True)
    # Unguessable public handle used in /affiliates/embed/<key>/ etc. NOT the pk
    # (which is also a UUID, but the key keeps the public surface decoupled from
    # the internal id and lets us rotate it without touching the row).
    key = models.CharField(max_length=43, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['affiliate', 'is_active']),
        ]

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f'{self.title or self.get_source_display()} ({self.key[:8]}…)'

    @property
    def effective_limit(self) -> int:
        """Result count, hard-capped so a public endpoint can't be coerced
        into rendering an unbounded grid."""
        return max(1, min(int(self.limit or 6), 24))


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
