"""Journal posts + block JSON.

`Block` is the immutable document body. We version the JSON so we
can add block types in later releases without losing the old
documents. The renderer keys on the version.
"""
from __future__ import annotations

from django.utils import timezone

from morpheus import models


class Post(models.Model):
    STATUS_CHOICES = (('draft', 'Draft'), ('scheduled', 'Scheduled'), ('published', 'Published'), ('archived', 'Archived'))

    slug = models.SlugField(unique=True, max_length=200, db_index=True)
    title = models.CharField(max_length=240)
    excerpt = models.TextField(blank=True)
    hero_image = models.URLField(blank=True)
    author = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='draft')
    publish_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Search meta: title + excerpt + first 1024 chars of the rendered text.
    search_blob = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-publish_at', '-created_at']
        indexes = [models.Index(fields=['status', '-publish_at'])]

    def is_live(self) -> bool:
        if self.status != 'published':
            return False
        return not (self.publish_at and self.publish_at > timezone.now())

    def __str__(self) -> str:
        return self.title


class Block(models.Model):
    """A single post's body as a versioned JSON document."""

    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name='body')
    version = models.PositiveIntegerField(default=1)
    # A JSON document of the shape:
    #   { "blocks": [{"type": ..., "data": ...}, ...] }
    document_json = models.TextField(default='{"version": 1, "blocks": []}')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'Block v{self.version} for {self.post_id}'
