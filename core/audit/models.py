"""Audit log — security-grade event trail."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """One immutable audit row.

    `event_type` is a free-form dotted slug (`rbac.role_granted`,
    `agents.approval_decided`, `payments.gateway_registered`). `target`
    is a human-readable identifier of the affected entity (`user/<id>`,
    `order/<number>`, `gateway/stripe`). `metadata` is whatever
    contextual JSON makes sense for that event.
    """

    SEVERITY_INFO = 'info'
    SEVERITY_WARNING = 'warning'
    SEVERITY_CRITICAL = 'critical'
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, 'Info'),
        (SEVERITY_WARNING, 'Warning'),
        (SEVERITY_CRITICAL, 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=120, db_index=True)
    severity = models.CharField(
        max_length=12, choices=SEVERITY_CHOICES, default=SEVERITY_INFO, db_index=True
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events',
    )
    actor_label = models.CharField(
        max_length=200, blank=True, help_text='Cached actor identifier (email/agent name).'
    )
    target = models.CharField(max_length=200, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', '-created_at']),
            models.Index(fields=['target', '-created_at']),
        ]

    def __str__(self) -> str:
        who = self.actor_label or (self.actor.email if self.actor else 'system')
        return f'{self.event_type} by {who} → {self.target}'
