"""Audiobook model — the narration attached to an audiobook ``ProductVariant``.

The audiobook EDITION is a real, purchasable catalog variant with its own
``variant_type='audiobook'`` (a downloadable, digital-behaving edition — no
shipping, delivered as a download); this row attaches the narration audio +
player metadata to that variant. A disabled plugin removes the player/generation
while the variant stays a plain audiobook edition. See
docs/plans/audiobooks-2026-06.md.
"""

from __future__ import annotations

import uuid

from django.db import models


class Audiobook(models.Model):
    STATUS_CHOICES = [
        ('none', 'None'),
        ('generating', 'Generating'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ]
    SOURCE_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('elevenlabs', 'ElevenLabs'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.OneToOneField(
        'catalog.ProductVariant', on_delete=models.CASCADE, related_name='audiobook'
    )
    audio_file = models.FileField(upload_to='audiobooks/', null=True, blank=True)
    sample_file = models.FileField(upload_to='audiobooks/samples/', null=True, blank=True)
    source_pdf = models.FileField(
        upload_to='audiobooks/source/',
        null=True,
        blank=True,
        help_text='Book PDF used as the narration source for ElevenLabs generation.',
    )
    narrator = models.CharField(max_length=200, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES, default='uploaded')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='none', db_index=True)
    elevenlabs_voice_id = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'audiobooks'

    def __str__(self) -> str:
        return f'Audiobook({self.variant_id}/{self.status})'

    @classmethod
    def for_product(cls, product):
        """The audiobook edition attached to a product (any status), or None."""
        return cls.objects.filter(variant__product=product).select_related('variant').first()

    @property
    def is_ready(self) -> bool:
        """True when there's a playable full track — gates the storefront player."""
        return self.status == 'ready' and bool(self.audio_file)
