"""Notification — one row per stack of events, per staff user."""

from __future__ import annotations

import uuid
from datetime import datetime

from django.conf import settings
from django.db import models

LEVELS = ('info', 'warning', 'urgent')
LEVEL_CHOICES = [('info', 'Info'), ('warning', 'Warning'), ('urgent', 'Urgent')]


class Notification(models.Model):
    """A single staff-facing notification, or a stack of repeats.

    `kind` is a coarse bucket (e.g. 'returns.requested', 'inventory.low',
    'agents.run_failed') used for filtering and per-user preferences;
    the title/body carry the human-readable copy. `action_url` is the
    URL clicking the row jumps to.

    A sender that names what the event is about (`services.notify(subject=…)`)
    gets a `group_key`; a repeat lands on the open stack with that key
    (unread, not archived) instead of a new row: `count` goes up, the copy
    becomes the latest, `occurrences` keeps the last 20 and `level` the
    highest. Reading or archiving closes the stack.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    kind = models.CharField(max_length=80, db_index=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    action_url = models.CharField(max_length=500, blank=True)
    icon = models.CharField(
        max_length=40,
        blank=True,
        default='bell',
        help_text='Lucide icon name; falls back to "bell".',
    )
    level = models.CharField(
        max_length=10, choices=LEVEL_CHOICES, default='info', db_default='info', db_index=True
    )
    group_key = models.CharField(max_length=200, blank=True, default='', db_default='')
    count = models.PositiveIntegerField(default=1, db_default=1)
    # Newest first: [{'at': iso, 'title': str, 'body': str}, …], at most 20.
    occurrences = models.JSONField(null=True, blank=True)
    # Latest activity. NULL on rows the release before wrote: order by
    # Coalesce(last_at, created_at) (services.ordered), never by this alone.
    last_at = models.DateTimeField(null=True, blank=True)
    snoozed_until = models.DateTimeField(null=True, blank=True, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'read_at']),
            models.Index(fields=['user', 'group_key'], name='notif_user_group_idx'),
        ]

    def __str__(self) -> str:
        return f'[{self.kind}] {self.title} ({"read" if self.read_at else "unread"})'

    @property
    def is_unread(self) -> bool:
        return self.read_at is None

    @property
    def activity_at(self):
        return self.last_at or self.created_at

    @property
    def history(self) -> list[dict]:
        """The stack's occurrences as stored, newest first (a single row has one)."""
        return list(self.occurrences or [])

    @property
    def timeline(self) -> list[dict]:
        """`history` with `at` parsed, for templates."""
        out = []
        for o in self.history:
            try:
                at = datetime.fromisoformat(o.get('at') or '')
            except (TypeError, ValueError):
                at = None
            out.append({'at': at, 'title': o.get('title') or '', 'body': o.get('body') or ''})
        return out

    @property
    def forgotten(self) -> int:
        """Repeats older than the occurrences a stack keeps."""
        return max(0, (self.count or 1) - len(self.history))


class NotificationPreference(models.Model):
    """What one staff member gets. Absent row = everything."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preference',
    )
    muted_kinds = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'Notification preferences for {self.user_id}'
