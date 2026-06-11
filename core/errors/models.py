"""ErrorEvent — one row per captured error (server 5xx or client JS).

The fingerprint column groups duplicates: same exception class +
short trace prefix → same fingerprint → one row in the grouped view
with a `seen` count, rather than N near-identical rows.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class ErrorEvent(models.Model):
    KIND_SERVER = 'server'
    KIND_CLIENT = 'client'
    KIND_CHOICES = [
        (KIND_SERVER, 'Server'),
        (KIND_CLIENT, 'Client (JS)'),
    ]

    LEVEL_ERROR = 'error'
    LEVEL_WARNING = 'warning'
    LEVEL_INFO = 'info'
    LEVEL_CHOICES = [
        (LEVEL_ERROR, 'Error'),
        (LEVEL_WARNING, 'Warning'),
        (LEVEL_INFO, 'Info'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_SERVER, db_index=True)
    level = models.CharField(
        max_length=10, choices=LEVEL_CHOICES, default=LEVEL_ERROR, db_index=True
    )

    # fingerprint = stable hash of (class, first ~3 trace frames or JS file:line).
    # Same fingerprint = same error; the list view groups by it.
    fingerprint = models.CharField(max_length=64, db_index=True)

    exception_class = models.CharField(max_length=200, blank=True)
    message = models.TextField(blank=True)
    traceback = models.TextField(blank=True)

    # Request context — present on both server and client errors when the
    # capture site can see them.
    path = models.CharField(max_length=500, blank=True, db_index=True)
    method = models.CharField(max_length=10, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    user_agent = models.CharField(max_length=400, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)

    # Free-form per-error context — JS error events carry `lineno`, `colno`,
    # `source_url`, `browser` here; server errors carry e.g. handler name.
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['fingerprint', '-created_at']),
            models.Index(fields=['kind', 'level', '-created_at']),
        ]

    def __str__(self) -> str:
        return f'{self.kind}:{self.exception_class or self.level} — {self.message[:60]}'
