"""Brand assets and design tokens.

`Asset` is a single uploaded file. `DesignTokenSet` is a named
collection of design tokens (colors, fonts, spacing, radii). The
storefront pulls the active set on every render and emits a CSS
stylesheet of variables.
"""
from __future__ import annotations

from morpheus import models


class Asset(models.Model):
    KIND_CHOICES = (('image', 'Image'), ('font', 'Font'), ('icon', 'Icon'), ('video', 'Video'), ('other', 'Other'))

    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default='image')
    url = models.URLField()
    tags = models.JSONField(default=list, blank=True)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['kind', '-created_at'])]


class DesignTokenSet(models.Model):
    slug = models.SlugField(unique=True, max_length=80)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=False)
    tokens_json = models.TextField(
        default='{}',
        help_text='Design tokens: {"colors": {"primary": "#..."}, "fonts": {...}, "spacing": {...}, "radii": {...}}',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', 'name']

    def __str__(self) -> str:
        return self.name
