"""
Per-merchant observability — metrics rollups & error logs.

`MerchantMetric` is a long, narrow append-only table with one row per
(channel, metric, bucket) where bucket is the truncated timestamp. The
rollup task collapses raw OutboxEvent rows into these buckets so the
dashboard can serve a fast time-series chart.
"""
from __future__ import annotations

import uuid

from morpheus import models


class MerchantMetric(models.Model):
    """A single metric value for a (channel, metric, bucket) triple."""
    GRANULARITY_CHOICES = [
        ('minute', 'Minute'),
        ('hour', 'Hour'),
        ('day', 'Day'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(
        'core.StoreChannel',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='metrics',
    )
    metric = models.CharField(max_length=80, db_index=True)
    granularity = models.CharField(max_length=10, choices=GRANULARITY_CHOICES, db_index=True)
    bucket = models.DateTimeField(db_index=True)
    value = models.FloatField(default=0)
    sample_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('channel', 'metric', 'granularity', 'bucket')
        indexes = [
            models.Index(fields=['metric', 'granularity', '-bucket']),
            models.Index(fields=['channel', 'metric', '-bucket']),
        ]

    def __str__(self) -> str:
        return f'{self.metric}@{self.bucket.isoformat()} = {self.value}'


class ErrorEvent(models.Model):
    """Captured exceptions / agent failures, indexed by channel for filtering."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(
        'core.StoreChannel',
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    source = models.CharField(max_length=40, db_index=True)
    message = models.TextField()
    stack_trace = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-occurred_at']
