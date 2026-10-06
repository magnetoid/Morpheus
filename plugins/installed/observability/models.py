"""
Per-merchant observability — the retired plugin error log.

The metrics rollup (`MerchantMetric`, fed from `core.OutboxEvent`) was removed
in v0.77.0: the outbox is only written when a NATS broker is configured, so on
every deployment without one the rollup had read nothing since 2026-07-12 and
its GraphQL series sat frozen at that date, unread by any dashboard surface.
"""

from __future__ import annotations

import uuid

from morpheus.app import models


class ErrorEvent(models.Model):
    """Captured exceptions / agent failures, indexed by channel for filtering."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.ForeignKey(
        'core.StoreChannel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    source = models.CharField(max_length=40, db_index=True)
    message = models.TextField()
    stack_trace = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-occurred_at']
