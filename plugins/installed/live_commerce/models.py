"""Live shopping events.

MVP scope: a scheduled event with an embedded stream (YouTube Live / any HLS
embed) and a set of pinned, buyable products. Own WebRTC, chat, and auto-VOD
re-encoding are explicitly out of scope this round.
"""

from __future__ import annotations

import uuid

from django.db import models


class LiveEvent(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('live', 'Live'),
        ('ended', 'Ended'),
    ]

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default='scheduled', db_index=True
    )
    embed_url = models.URLField(help_text='YouTube Live / any HLS embed URL')
    recording_url = models.URLField(
        blank=True, help_text='Set after the event → page becomes a replay'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'live_commerce'
        ordering = ['-scheduled_start']
        indexes = [models.Index(fields=['status', 'scheduled_start'])]

    def __str__(self) -> str:
        return self.title

    @property
    def is_replay(self) -> bool:
        return self.status == 'ended' and bool(self.recording_url)


class LiveEventProduct(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    event = models.ForeignKey(LiveEvent, on_delete=models.CASCADE, related_name='products')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='+')
    sort_order = models.PositiveIntegerField(default=0)
    pinned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'live_commerce'
        ordering = ['sort_order', 'pinned_at']
        unique_together = ('event', 'product')

    def __str__(self) -> str:
        return f'{self.event.slug} · {self.product_id}'
