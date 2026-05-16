"""Product video attachments for the PDP.

One row per video. The storefront renders these into a slot above the
long description; the merchant edits them via the Django admin (no full
dashboard surface yet — adding videos one-at-a-time per product is rare
enough that the admin is fine).
"""
from __future__ import annotations

import uuid

from django.db import models


class ProductVideo(models.Model):
    """A single video attached to a product.

    ``url`` accepts YouTube / Vimeo / direct mp4 links — the block
    template auto-detects and generates the appropriate embed. For
    anything unusual the merchant can paste raw iframe HTML into
    ``embed_html`` and that wins over ``url``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE, related_name='videos',
    )
    title = models.CharField(max_length=200, blank=True)
    url = models.URLField(
        blank=True,
        help_text='YouTube, Vimeo, or direct video URL. Auto-converted to an embed.',
    )
    embed_html = models.TextField(
        blank=True,
        help_text='Optional raw iframe HTML. Overrides `url` when set.',
    )
    poster_url = models.URLField(
        blank=True,
        help_text='Optional poster/thumbnail image URL (used for non-YouTube/Vimeo embeds).',
    )
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'created_at']
        indexes = [
            models.Index(fields=['product', 'is_active', 'sort_order']),
        ]

    def __str__(self) -> str:
        return self.title or self.url or f'Video {self.id}'
