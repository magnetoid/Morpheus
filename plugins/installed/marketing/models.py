"""
Morpheus CMS - Marketing Models
Coupons, Discounts, Email Campaigns, SEO Redirects
"""

import uuid

from django.utils import timezone
from djmoney.models.fields import MoneyField

from morpheus.app import models


class Coupon(models.Model):
    DISCOUNT_TYPES = [
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
        ('free_shipping', 'Free Shipping'),
        ('buy_x_get_y', 'Buy X Get Y'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=15, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    minimum_order_amount = MoneyField(
        max_digits=14, decimal_places=2, default_currency='USD', null=True, blank=True
    )
    maximum_discount_amount = MoneyField(
        max_digits=14, decimal_places=2, default_currency='USD', null=True, blank=True
    )

    # Constraints
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    usage_limit_per_customer = models.PositiveIntegerField(null=True, blank=True)
    times_used = models.PositiveIntegerField(default=0)

    # Applicability
    applicable_products = models.ManyToManyField('catalog.Product', blank=True)
    applicable_categories = models.ManyToManyField('catalog.Category', blank=True)
    applicable_collections = models.ManyToManyField('catalog.Collection', blank=True)
    exclude_sale_items = models.BooleanField(default=False)

    # Validity
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} ({self.discount_type})'

    @property
    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.expires_at and now > self.expires_at:
            return False
        if self.usage_limit and self.times_used >= self.usage_limit:  # noqa: SIM103
            return False
        return True


class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE)
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    discount_amount = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('coupon', 'order')


class Redirect(models.Model):
    """301/302 URL redirects for SEO migrations."""

    REDIRECT_TYPES = [('301', '301 Permanent'), ('302', '302 Temporary')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_path = models.CharField(max_length=500, unique=True)
    to_path = models.CharField(max_length=500)
    redirect_type = models.CharField(max_length=3, choices=REDIRECT_TYPES, default='301')
    is_active = models.BooleanField(default=True)
    hits = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['from_path']

    def __str__(self):
        return f'{self.from_path} → {self.to_path}'


class EmailCampaign(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    subject = models.CharField(max_length=200)
    preview_text = models.CharField(max_length=300, blank=True)
    html_body = models.TextField()
    text_body = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    recipient_count = models.PositiveIntegerField(default=0)
    open_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name
