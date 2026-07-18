"""Newsletter models — the subscriber list (with double opt-in) and signup
popups. Sending is NOT owned here: it reuses `marketing.EmailCampaign`
(Phase 3). See docs/plans/newsletter.md.
"""

from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from django.db import models


class NewsletterSubscriber(models.Model):
    """One email on the list. Double opt-in: only ``confirmed`` rows are
    mailable; ``unsubscribed`` is terminal."""

    STATUS_CHOICES = [
        ('pending', 'Pending confirmation'),
        ('confirmed', 'Confirmed'),
        ('unsubscribed', 'Unsubscribed'),
    ]
    SOURCE_CHOICES = [
        ('popup', 'Signup popup'),
        ('form', 'Storefront form'),
        ('checkout', 'Checkout'),
        ('manual', 'Manual / dashboard'),
        ('import', 'Import'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default='pending', db_index=True
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='newsletter_subscriptions',
    )
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES, default='popup')
    confirm_token = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    tags = models.JSONField(default=list, blank=True)  # segmentation
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', '-created_at'])]

    def __str__(self) -> str:
        return f'{self.email} ({self.status})'


class SignupPopup(models.Model):
    """A marketing email-capture popup (distinct from cookie consent). Trigger +
    frequency drive when it shows; captures into NewsletterSubscriber."""

    TRIGGER_CHOICES = [
        ('immediate', 'On page load'),
        ('time_delay', 'After N seconds'),
        ('exit_intent', 'On exit intent'),
        ('scroll_depth', 'After scrolling N%'),
    ]
    FREQUENCY_CHOICES = [
        ('once', 'Once per visitor'),
        ('daily', 'Once per day'),
        ('every_visit', 'Every visit'),
    ]
    AUDIENCE_CHOICES = [
        ('all', 'All visitors'),
        ('new', 'New visitors'),
        ('returning', 'Returning visitors'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    enabled = models.BooleanField(default=False, db_index=True)
    headline = models.CharField(max_length=200, default='Join our newsletter')
    body = models.TextField(blank=True, default='Get the latest news and offers.')
    button_label = models.CharField(max_length=60, default='Subscribe')
    success_message = models.CharField(max_length=200, default='Thanks — check your inbox!')

    trigger = models.CharField(max_length=12, choices=TRIGGER_CHOICES, default='time_delay')
    trigger_value = models.PositiveIntegerField(
        default=5, help_text='Seconds (time_delay) or percent (scroll_depth).'
    )
    frequency = models.CharField(max_length=12, choices=FREQUENCY_CHOICES, default='once')
    audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default='all')

    incentive = models.CharField(
        max_length=120, blank=True, help_text='e.g. "10% off your first order".'
    )
    coupon_code = models.CharField(max_length=60, blank=True)

    impressions = models.PositiveIntegerField(default=0)
    conversions = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self) -> str:
        return f'{self.name} ({"on" if self.enabled else "off"})'


class CampaignSend(models.Model):
    """Per-recipient send log — the idempotency ledger for bulk mail.

    One row per enqueue. For campaign sends (``kind='campaign'``, FK to
    ``marketing.EmailCampaign`` — cross-plugin FK sanctioned by
    ``requires=['marketing']``) it makes a re-run of ``send_campaign`` skip
    already-mailed recipients. For lifecycle sends with no campaign row
    (``kind='winback'``) it is the dedupe window.
    """

    KIND_CHOICES = [
        ('campaign', 'Campaign'),
        ('winback', 'Win-back'),
        ('test', 'Test send'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        'marketing.EmailCampaign',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sends',
    )
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default='campaign')
    email = models.EmailField(db_index=True)
    ok = models.BooleanField(default=True)
    detail = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['campaign', 'email']),
            models.Index(fields=['kind', 'email', '-created_at']),
        ]

    def __str__(self) -> str:
        return f'{self.kind} → {self.email} ({"ok" if self.ok else "failed"})'
