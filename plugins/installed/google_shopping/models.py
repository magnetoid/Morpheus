"""Google Shopping models.

Only an audit log — the feed itself is computed on demand from the catalog,
and all configuration lives in PluginConfig (no secrets in the DB schema).
"""

from __future__ import annotations

import uuid

from django.db import models


class GoogleSyncLog(models.Model):
    """One row per feed build / Content-API push / Ads sync — the audit trail
    shown on the dashboard so a silent feed failure stops hiding."""

    KIND_FEED = 'feed'
    KIND_CONTENT_API = 'content_api'
    KIND_ADS = 'ads'
    KIND_CHOICES = [
        (KIND_FEED, 'Feed build'),
        (KIND_CONTENT_API, 'Content API push'),
        (KIND_ADS, 'Ads sync'),
    ]
    STATUS_OK = 'ok'
    STATUS_PARTIAL = 'partial'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [
        (STATUS_OK, 'OK'),
        (STATUS_PARTIAL, 'Partial'),
        (STATUS_ERROR, 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_FEED)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OK)
    item_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['kind', '-created_at'])]

    def __str__(self):
        return f'{self.kind} {self.status} ({self.item_count} items) @ {self.created_at:%Y-%m-%d %H:%M}'
