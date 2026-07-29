"""Webhook delivery log."""

from __future__ import annotations

import uuid

from morpheus.plugin import models


class WebhookDelivery(models.Model):
    """One attempt to deliver an event to a `WebhookEndpoint`."""

    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('delivering', 'Delivering'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('retrying', 'Retrying'),
        ('dlq', 'Dead-letter (max retries)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    endpoint = models.ForeignKey(
        'core.WebhookEndpoint',
        on_delete=models.CASCADE,
        related_name='deliveries',
    )
    event_name = models.CharField(max_length=120, db_index=True)
    payload = models.JSONField(default=dict)

    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default='queued', db_index=True
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['endpoint', '-created_at']),
            models.Index(fields=['status', 'next_retry_at']),
        ]
