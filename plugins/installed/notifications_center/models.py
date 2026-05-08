"""Notification — one row per fan-out event, per staff user."""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    """A single staff-facing notification.

    `kind` is a coarse bucket (e.g. 'returns.requested', 'inventory.low',
    'agents.run_failed') used for filtering and per-user preferences;
    the title/body carry the human-readable copy. `action_url` is the
    URL clicking the row jumps to.

    The model is intentionally minimal — no severity, no tags, no
    attachments. Add fields here when a real use case demands them
    rather than upfront.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications',
    )
    kind = models.CharField(max_length=80, db_index=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    action_url = models.CharField(max_length=500, blank=True)
    icon = models.CharField(max_length=40, blank=True, default='bell',
                            help_text='Lucide icon name; falls back to "bell".')
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'read_at']),
        ]

    def __str__(self) -> str:
        return f'[{self.kind}] {self.title} ({"read" if self.read_at else "unread"})'

    @property
    def is_unread(self) -> bool:
        return self.read_at is None
