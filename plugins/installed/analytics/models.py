"""
Analytics models.

Two storage tiers:

* **AnalyticsEvent** — hot, append-only event log. Indexed by name + time
  + session. Trimmed by a Celery beat task (default: keep 90 days).
* **DailyMetric** — pre-rolled daily aggregates. Cheap to query, kept
  indefinitely. Used by dashboard charts and agent tools.

Plus:
* **AnalyticsSession** — visitor session: cookie id, customer FK once
  authenticated, device/browser hints, UTM source.
* **FunnelDefinition** — merchant-defined ordered list of event names;
  the funnel report walks it.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from djmoney.models.fields import MoneyField

from morpheus.plugin import models


class AnalyticsSession(models.Model):
    """One visitor session, identified by a long-lived analytics cookie."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cookie_id = models.CharField(max_length=64, unique=True, db_index=True)
    cross_device_id = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
        help_text='Anonymized ID for cross-device tracking',
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analytics_sessions',
    )
    is_consented = models.BooleanField(default=False, help_text='GDPR/CCPA consent status')
    user_agent = models.CharField(max_length=300, blank=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    device = models.CharField(max_length=20, blank=True)
    device_specs = models.JSONField(
        default=dict, blank=True, help_text='Browser, OS, screen size, network conditions'
    )
    geo_location = models.JSONField(
        default=dict, blank=True, help_text='Country, region, city from IP'
    )
    referrer = models.CharField(max_length=500, blank=True)
    landing_url = models.CharField(max_length=500, blank=True)

    utm_source = models.CharField(max_length=80, blank=True, db_index=True)
    utm_medium = models.CharField(max_length=80, blank=True)
    utm_campaign = models.CharField(max_length=120, blank=True)
    utm_content = models.CharField(max_length=120, blank=True)

    first_seen_at = models.DateTimeField(auto_now_add=True, db_index=True)
    last_seen_at = models.DateTimeField(auto_now=True, db_index=True)
    session_duration = models.PositiveIntegerField(default=0, help_text='Duration in seconds')
    event_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-last_seen_at']
        indexes = [
            models.Index(fields=['customer', '-last_seen_at']),
            models.Index(fields=['utm_source', '-first_seen_at']),
            models.Index(fields=['cross_device_id', '-last_seen_at']),
        ]


class AnalyticsEvent(models.Model):
    """Append-only event log."""

    KIND_CHOICES = [
        ('pageview', 'Page view'),
        ('product_view', 'Product view'),
        ('search', 'Search'),
        ('cart', 'Cart event'),
        ('checkout', 'Checkout event'),
        ('purchase', 'Purchase'),
        ('refund', 'Refund'),
        ('signup', 'Signup'),
        ('login', 'Login'),
        ('agent_run', 'Agent run'),
        ('error', 'Error'),
        ('custom', 'Custom'),
        ('click', 'Button Click'),
        ('form_submit', 'Form Submission'),
        ('scroll', 'Scroll Depth'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, db_index=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='custom', db_index=True)

    session = models.ForeignKey(
        AnalyticsSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events',
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analytics_events',
    )

    url = models.CharField(max_length=500, blank=True)
    product_slug = models.CharField(max_length=200, blank=True, db_index=True)
    search_query = models.CharField(max_length=200, blank=True, db_index=True)
    revenue = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='USD',
        null=True,
        blank=True,
    )
    agent_name = models.CharField(max_length=100, blank=True, db_index=True)

    scroll_depth = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text='Percentage 0-100'
    )
    duration_ms = models.PositiveIntegerField(
        null=True, blank=True, help_text='Interaction duration in ms'
    )
    error_context = models.JSONField(
        default=dict, blank=True, help_text='Stack trace, API failure details'
    )
    is_realtime = models.BooleanField(
        default=False, db_index=True, help_text='Flag for real-time stream ingestion'
    )
    idempotency_key = models.CharField(
        max_length=64, blank=True, db_index=True, help_text='Used for deduplication'
    )

    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name', '-created_at']),
            models.Index(fields=['kind', '-created_at']),
            models.Index(fields=['session', '-created_at']),
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['agent_name', '-created_at']),
            models.Index(fields=['is_realtime', '-created_at']),
        ]


class DailyMetric(models.Model):
    """One row per (day, metric_name, dimension_value)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    day = models.DateField(db_index=True)
    metric = models.CharField(max_length=80, db_index=True)
    dimension = models.CharField(max_length=120, blank=True, db_index=True)
    value_int = models.BigIntegerField(default=0)
    value_money = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='USD',
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['-day', 'metric']
        unique_together = ('day', 'metric', 'dimension')
        indexes = [
            models.Index(fields=['metric', '-day']),
        ]


class FunnelDefinition(models.Model):
    """A named ordered list of event names."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    description = models.CharField(max_length=300, blank=True)
    steps = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CustomEventConfig(models.Model):
    """No-code configuration for business-specific metric tracking."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    css_selector = models.CharField(
        max_length=255, blank=True, help_text='CSS selector to track clicks/forms'
    )
    url_pattern = models.CharField(
        max_length=255, blank=True, help_text='Regex for matching specific URLs'
    )
    event_kind = models.CharField(
        max_length=20, choices=AnalyticsEvent.KIND_CHOICES, default='custom'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AnalyticsExport(models.Model):
    """Scheduled or one-off analytics exports."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    format = models.CharField(
        max_length=10, choices=[('csv', 'CSV'), ('json', 'JSON'), ('pdf', 'PDF')]
    )
    schedule_cron = models.CharField(
        max_length=100, blank=True, help_text='Cron format for automated delivery'
    )
    date_range_days = models.PositiveIntegerField(default=30)
    filters = models.JSONField(default=dict, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AdSpendSnapshot(models.Model):
    """Ad spend per (day, channel), collected nightly from channel plugins via the
    ANALYTICS_AD_SPEND filter. Divides attributed revenue to give per-channel ROAS."""

    day = models.DateField(db_index=True)
    channel = models.CharField(max_length=40, db_index=True)
    spend = MoneyField(max_digits=14, decimal_places=2, default_currency='USD')
    source_meta = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'analytics_ad_spend'
        unique_together = ('day', 'channel')
        ordering = ['-day']

    def __str__(self) -> str:
        return f'{self.day} {self.channel}: {self.spend}'
