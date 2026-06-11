"""
Environments — dev / staging / production.

A merchant typically has one production environment plus 0–N dev/staging
environments that act as drafts for theme/config/content changes. Catalog,
inventory, orders intentionally remain shared across environments — those
are LIVE data and you don't want a dev branch of customer orders.

Environments primarily isolate:
- Theme bundle + active theme name
- StoreSettings overrides
- Plugin config overrides
- Promotional content

Promotion: a Snapshot of one environment can be applied to another, with
preview + dry-run + rollback.
"""

from __future__ import annotations

import uuid

from django.conf import settings

from morpheus import models


class Environment(models.Model):
    KIND_CHOICES = [
        ('development', 'Development'),
        ('staging', 'Staging'),
        ('production', 'Production'),
        ('preview', 'Preview / PR'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    kind = models.CharField(
        max_length=15, choices=KIND_CHOICES, default='development', db_index=True
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
    )
    is_protected = models.BooleanField(
        default=False,
        help_text='Mutations require an explicit confirm flag (typically true for production).',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    settings_overrides = models.JSONField(default=dict, blank=True)
    theme_overrides = models.JSONField(default=dict, blank=True)
    domain = models.CharField(max_length=200, blank=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['kind', 'name']
        indexes = [
            models.Index(fields=['kind', 'is_active']),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.kind})'


class EnvironmentSnapshot(models.Model):
    """A point-in-time capture of an environment's overrides. Promotion = applying a snapshot to another env."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    environment = models.ForeignKey(
        Environment,
        on_delete=models.CASCADE,
        related_name='snapshots',
    )
    label = models.CharField(max_length=200, blank=True)
    payload = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Deployment(models.Model):
    """A snapshot promoted from one environment into another."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('applied', 'Applied'),
        ('rolled_back', 'Rolled Back'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    snapshot = models.ForeignKey(EnvironmentSnapshot, on_delete=models.CASCADE)
    target = models.ForeignKey(
        Environment,
        on_delete=models.CASCADE,
        related_name='deployments',
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default='pending', db_index=True
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    note = models.TextField(blank=True)
    diff = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
