"""Reviews model — minimal write/render flow for the storefront PDP.

PDP template iterates ``product.reviews.all`` and uses ``body``, ``rating``,
``customer.full_name``, and ``created_at``. This model satisfies that contract
without speculative fields. Add moderation states / helpfulness votes later
when actual UX requires them.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Review(models.Model):
    STATUS_CHOICES = [
        ('published', 'Published'),
        ('pending',   'Pending moderation'),
        ('hidden',    'Hidden'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE, related_name='reviews',
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviews',
    )
    rating = models.PositiveSmallIntegerField(default=5, help_text='1–5 stars.')
    body = models.TextField()
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default='published', db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['product', '-created_at'])]
