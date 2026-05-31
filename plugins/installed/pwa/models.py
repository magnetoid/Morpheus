"""PWA models — push subscription registry.

One row per (visitor browser, push endpoint). The endpoint + auth + p256dh
trio is what the Web Push protocol uses; we keep them server-side so the
notifications app can target them by audience (cart-abandon recovery,
back-in-stock alerts, order updates).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    """One Web Push subscription. Endpoint uniqueness is enforced —
    the same browser re-subscribing updates auth/p256dh in-place."""

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='push_subscriptions',
    )
    visitor_id = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
        help_text='Anonymous cookie id when no auth user; experiments-compat',
    )
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=200)
    user_agent = models.CharField(max_length=300, blank=True)
    topics = models.JSONField(
        default=list,
        blank=True,
        help_text='Subscribed topics (e.g. ["cart_recovery","back_in_stock"])',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'pwa_push_subscription'
        indexes = [
            models.Index(fields=['customer', '-created_at'], name='pwa_push_cust_idx'),
        ]

    def __str__(self) -> str:
        return f'PushSub {self.pk} ({self.customer_id or self.visitor_id[:10]})'
