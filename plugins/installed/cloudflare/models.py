"""
Cloudflare plugin — models.

A `CloudflareAccount` holds API credentials for one Cloudflare account.
A `CloudflareZone` represents a zone (domain) the merchant manages and the
operations Morpheus can run against it (cache purge, DNS update).
A `CacheInvalidation` audit row records every purge for the dashboard.
"""
from __future__ import annotations

import uuid

from morpheus import models


class CloudflareAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    label = models.CharField(max_length=100, default='default')
    account_id = models.CharField(max_length=64, blank=True)
    api_token = models.CharField(
        max_length=256,
        help_text='Cloudflare API token with Zone:Cache Purge + Zone:DNS:Edit scopes.',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['label']

    def __str__(self) -> str:
        return f'CloudflareAccount({self.label})'


class CloudflareZone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        CloudflareAccount, on_delete=models.CASCADE, related_name='zones',
    )
    channel = models.ForeignKey(
        'core.StoreChannel',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cloudflare_zones',
        help_text='Optional StoreChannel scope. Null = applies to all channels.',
    )
    zone_id = models.CharField(max_length=64, db_index=True)
    domain = models.CharField(max_length=200, db_index=True)
    auto_purge_on_product_update = models.BooleanField(default=True)
    auto_purge_on_collection_update = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True, db_index=True)
    last_purge_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('account', 'zone_id')
        ordering = ['domain']

    def __str__(self) -> str:
        return f'CloudflareZone({self.domain})'


class CacheInvalidation(models.Model):
    """One row per purge call. The merchant sees this in the observability dashboard."""

    SCOPE_CHOICES = [
        ('urls', 'URLs'),
        ('tags', 'Cache Tags'),
        ('hosts', 'Hosts'),
        ('purge_everything', 'Purge Everything'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(CloudflareZone, on_delete=models.CASCADE, related_name='invalidations')
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    targets = models.JSONField(default=list, help_text='URLs / tags / hosts purged.')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    triggered_by = models.CharField(max_length=120, blank=True)
    response = models.JSONField(default=dict)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['zone', '-created_at']),
        ]
