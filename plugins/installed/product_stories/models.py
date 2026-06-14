"""Product story blocks — the scroll-snap "why you'll love it" panels on the
product page (image + heading + body), ordered per product. A real, editable
content model (the immersive_pdp story_rail was a data-less shell).
"""

from __future__ import annotations

import uuid

from django.db import models


class ProductStoryBlock(models.Model):
    LAYOUT_CHOICES = [
        ('image_right', 'Image right'),
        ('image_left', 'Image left'),
        ('image_full', 'Full-width image'),
        ('text', 'Text only'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE, related_name='story_blocks'
    )
    order = models.PositiveSmallIntegerField(default=0, db_index=True)
    eyebrow = models.CharField(
        max_length=60, blank=True, help_text='Small label above the heading.'
    )
    heading = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    image_url = models.CharField(max_length=500, blank=True, help_text='Optional image URL.')
    layout = models.CharField(max_length=12, choices=LAYOUT_CHOICES, default='image_right')
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['product', 'order', 'created_at']
        indexes = [models.Index(fields=['product', 'is_active', 'order'])]

    def __str__(self) -> str:
        return f'Story[{self.product_id}/{self.order}]: {self.heading[:40]}'
