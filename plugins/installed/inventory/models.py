"""
Morpheus CMS - Inventory Models
Stock tracking, warehouses, stock movements
"""

import uuid

from django.conf import settings
from django.db import transaction

from morpheus import models


class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    address = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', 'name']

    def __str__(self):
        return self.name


class StockLevel(models.Model):
    """Current stock per variant per warehouse."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(
        'catalog.ProductVariant', on_delete=models.CASCADE, related_name='stock_levels'
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stock_levels')
    quantity = models.IntegerField(default=0)
    reserved_quantity = models.IntegerField(default=0)  # held for pending orders
    reorder_point = models.IntegerField(default=5)
    reorder_quantity = models.IntegerField(default=20)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('variant', 'warehouse')

    def __str__(self):
        return f'{self.variant} @ {self.warehouse}: {self.available_quantity}'

    @property
    def available_quantity(self):
        return max(0, self.quantity - self.reserved_quantity)

    @property
    def is_low_stock(self):
        return self.available_quantity <= self.reorder_point

    @property
    def is_out_of_stock(self):
        return self.available_quantity <= 0


class StockMovement(models.Model):
    """Audit log of every stock change."""

    MOVEMENT_TYPES = [
        ('receive', 'Stock Received'),
        ('sale', 'Sale'),
        ('return', 'Customer Return'),
        ('adjustment', 'Manual Adjustment'),
        ('transfer', 'Warehouse Transfer'),
        ('damage', 'Damaged / Written Off'),
        ('reserve', 'Reserved'),
        ('unreserve', 'Unreserved'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stock_level = models.ForeignKey(StockLevel, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=15, choices=MOVEMENT_TYPES)
    quantity_change = models.IntegerField()  # positive = in, negative = out
    quantity_before = models.IntegerField()
    quantity_after = models.IntegerField()
    reference = models.CharField(
        max_length=200, blank=True, help_text='Order number, PO number, etc.'
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'customers.Customer', on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.movement_type}: {self.quantity_change:+d} for {self.stock_level.variant}'

    @classmethod
    def record(cls, stock_level, movement_type, quantity_change, reference='', notes='', user=None):
        """Atomically update stock and record movement."""
        with transaction.atomic():
            sl = StockLevel.objects.select_for_update().get(pk=stock_level.pk)
            before = sl.quantity
            sl.quantity += quantity_change
            sl.save()
            return cls.objects.create(
                stock_level=sl,
                movement_type=movement_type,
                quantity_change=quantity_change,
                quantity_before=before,
                quantity_after=sl.quantity,
                reference=reference,
                notes=notes,
                created_by=user,
            )


class BackInStockSubscription(models.Model):
    """Email me when this product is back in stock."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.CASCADE,
        related_name='back_in_stock_subs',
    )
    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='back_in_stock_subs',
    )
    email = models.EmailField(db_index=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='back_in_stock_subs',
    )
    notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('product', 'variant', 'email')
        indexes = [
            models.Index(fields=['product', 'notified_at']),
            models.Index(fields=['variant', 'notified_at']),
        ]


class StockoutAlert(models.Model):
    """An open episode where a variant is projected to stock out within the
    reorder window. Created by sync_stockout_alerts(); one OPEN row per
    variant (partial unique constraint) so merchants are alerted once per
    episode, not nagged on every forecast run."""

    STATUS_CHOICES = [('open', 'Open'), ('resolved', 'Resolved')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.ForeignKey(
        'catalog.ProductVariant', on_delete=models.CASCADE, related_name='stockout_alerts'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open', db_index=True)
    days_of_cover = models.FloatField(null=True, blank=True)
    daily_velocity = models.FloatField(default=0)
    suggested_reorder_qty = models.IntegerField(default=0)
    opened_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['days_of_cover']
        constraints = [
            models.UniqueConstraint(
                fields=['variant'],
                condition=models.Q(status='open'),
                name='uniq_open_stockout_alert_per_variant',
            )
        ]
        indexes = [models.Index(fields=['status', 'days_of_cover'])]

    def __str__(self):
        return f'StockoutAlert({self.variant} — {self.status})'
