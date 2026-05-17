"""tracking plugin — models.

Two tables:

* ``TrackingSettings`` is the singleton control center the merchant
  configures from `/dashboard/tracking/settings/`. Holds the GA4
  measurement ID, the encrypted API secret, the GTM container ID, the
  Consent Mode v2 defaults, and per-event enable flags.

* ``GA4EventLog`` is an append-only audit row written by the
  Measurement Protocol service for every server-side hit. The
  dashboard ``/dashboard/tracking/`` shows the latest rows + lets
  the merchant inspect payload/response for debugging.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


# Sensible defaults — the dashboard initialises a singleton on first
# load with these values, then the merchant edits in place.
DEFAULT_EVENT_FIRING = {
    'page_view': True,
    'view_item': True,
    'view_item_list': True,
    'add_to_cart': True,
    'begin_checkout': True,
    'purchase': True,
    'refund': True,
    'sign_up': True,
    'login': True,
    'search': True,
}

DEFAULT_CONSENT_DEFAULT = {
    'ad_storage': 'denied',
    'analytics_storage': 'denied',
    'ad_user_data': 'denied',
    'ad_personalization': 'denied',
}

DEFAULT_ENHANCED_OVERRIDES = {
    'scroll': True,
    'outbound_click': True,
    'file_download': True,
    'video_engagement': True,
}


class TrackingSettings(models.Model):
    """Singleton — merchant config for GA4 + GTM."""

    REGION_CHOICES = [
        ('global', 'Global (www.google-analytics.com)'),
        ('eu', 'European Union (region1.google-analytics.com)'),
    ]

    BANNER_PLACEMENT_CHOICES = [
        ('bottom', 'Bottom banner'),
        ('corner', 'Corner card'),
        ('modal', 'Blocking modal'),
    ]

    DEDUP_STRATEGY_CHOICES = [
        ('transaction_id', 'By transaction_id (recommended for purchases)'),
        ('client_window', 'By client_id + event_name + window'),
        ('off', 'No deduplication'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Connection ─────────────────────────────────────────────────────
    measurement_id = models.CharField(max_length=32, blank=True,
                                      help_text='GA4 stream ID, e.g. G-XXXXXXXXXX')
    api_secret = models.CharField(max_length=120, blank=True,
                                  help_text='API secret for the data stream — used by Measurement Protocol.')
    gtm_container_id = models.CharField(max_length=32, blank=True,
                                        help_text='GTM web container, e.g. GTM-XXXXXXX')
    sgtm_server_url = models.URLField(max_length=500, blank=True,
                                      help_text='Optional server-side GTM endpoint (Cloud Run / Stape).')
    region = models.CharField(max_length=10, choices=REGION_CHOICES, default='global')

    # ── Event firing ───────────────────────────────────────────────────
    server_side_enabled = models.BooleanField(default=True)
    client_side_enabled = models.BooleanField(default=True)
    debug_mode = models.BooleanField(default=False,
                                     help_text='Appends ?debug_mode=1 to MP requests — visible in DebugView, not standard reports.')
    event_firing = models.JSONField(default=dict, blank=True,
                                    help_text='Per-event enable map, e.g. {"purchase": true, "view_item": true}.')
    enhanced_overrides = models.JSONField(default=dict, blank=True,
                                          help_text='Override GA4 Enhanced Measurement defaults.')

    # ── Consent Mode v2 ───────────────────────────────────────────────
    consent_default = models.JSONField(default=dict, blank=True,
                                       help_text='Default state per signal — granted/denied per ad_storage, analytics_storage, ad_user_data, ad_personalization.')
    show_consent_banner = models.BooleanField(default=False)
    banner_accept_label = models.CharField(max_length=40, default='Accept all')
    banner_reject_label = models.CharField(max_length=40, default='Reject')
    banner_body = models.CharField(max_length=400,
                                   default='We use cookies for analytics and a great shopping experience.')
    banner_link_url = models.CharField(max_length=400, blank=True)
    banner_placement = models.CharField(max_length=10, choices=BANNER_PLACEMENT_CHOICES, default='bottom')

    # ── Identity ──────────────────────────────────────────────────────
    user_id_enabled = models.BooleanField(default=False,
                                          help_text='Send hashed customer pk as GA4 user_id when authenticated.')
    cross_domain = models.CharField(max_length=400, blank=True,
                                    help_text='Comma-separated additional domains for cross-domain measurement.')

    # ── Filters & dedup ───────────────────────────────────────────────
    block_paths = models.JSONField(default=list, blank=True,
                                   help_text='Path prefixes to never track (e.g. ["/admin/", "/dashboard/"]).')
    bot_patterns = models.JSONField(default=list, blank=True,
                                    help_text='User-Agent substrings to never track.')
    dedup_strategy = models.CharField(max_length=20, choices=DEDUP_STRATEGY_CHOICES,
                                      default='transaction_id')
    dedup_window_minutes = models.PositiveSmallIntegerField(default=60)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tracking settings'
        verbose_name_plural = 'Tracking settings'

    def __str__(self) -> str:
        return self.measurement_id or 'Tracking settings'

    @classmethod
    def get_solo(cls) -> 'TrackingSettings':
        """Return the singleton row, creating it with defaults if missing."""
        row, created = cls.objects.get_or_create(pk=cls.objects.values_list('id', flat=True).first())
        if created or not row.event_firing:
            row.event_firing = {**DEFAULT_EVENT_FIRING, **(row.event_firing or {})}
        if created or not row.consent_default:
            row.consent_default = {**DEFAULT_CONSENT_DEFAULT, **(row.consent_default or {})}
        if created or not row.enhanced_overrides:
            row.enhanced_overrides = {**DEFAULT_ENHANCED_OVERRIDES, **(row.enhanced_overrides or {})}
        if created:
            row.save()
        return row

    def event_enabled(self, name: str) -> bool:
        return bool((self.event_firing or {}).get(name, True))

    def is_path_blocked(self, path: str) -> bool:
        for prefix in (self.block_paths or []):
            if prefix and path.startswith(prefix):
                return True
        return False


class GA4EventLog(models.Model):
    """Append-only record of every server-side Measurement Protocol hit."""

    STATUS_SENT = 'sent'
    STATUS_ERROR = 'error'
    STATUS_DEDUPED = 'deduped'
    STATUS_DISABLED = 'disabled'

    STATUS_CHOICES = [
        (STATUS_SENT, 'Sent'),
        (STATUS_ERROR, 'Error'),
        (STATUS_DEDUPED, 'Deduplicated'),
        (STATUS_DISABLED, 'Disabled (event firing off)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_name = models.CharField(max_length=80, db_index=True)
    transaction_id = models.CharField(max_length=80, blank=True, db_index=True)
    client_id = models.CharField(max_length=80, blank=True, db_index=True)
    session_id = models.CharField(max_length=80, blank=True)
    user_id = models.CharField(max_length=80, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_SENT, db_index=True)
    error_message = models.CharField(max_length=400, blank=True)
    fired_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-fired_at']
        indexes = [
            models.Index(fields=['event_name', '-fired_at']),
            models.Index(fields=['status', '-fired_at']),
        ]

    def __str__(self) -> str:
        return f'{self.event_name} @ {self.fired_at:%Y-%m-%d %H:%M:%S}'
