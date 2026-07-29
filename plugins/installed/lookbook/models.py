"""Lookbook: a hand-authored or AI-generated editorial bundle."""

from __future__ import annotations

from morpheus.plugin import models


class Look(models.Model):
    slug = models.SlugField(unique=True, max_length=120, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    cover_image = models.URLField(blank=True)
    is_published = models.BooleanField(default=True)
    is_auto_generated = models.BooleanField(default=False)
    products = models.ManyToManyField(
        'catalog.Product',
        related_name='+',
        through='LookItem',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class LookItem(models.Model):
    look = models.ForeignKey(Look, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', on_delete=models.CASCADE, related_name='+')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ('look', 'product')
