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
        ('earn_order',  'Earned on order'),
        ('spend_order', 'Redeemed on order'),
        ('adjust',      'Manual adjustment'),
        ('expire',      'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
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
