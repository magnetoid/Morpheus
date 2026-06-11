"""Translation row — one per (object, language_code, field)."""

from __future__ import annotations

import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Translation(models.Model):
    """Translation overlay on any model field."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    target = GenericForeignKey('content_type', 'object_id')

    field = models.CharField(max_length=80, db_index=True)
    language_code = models.CharField(
        max_length=10, db_index=True, help_text='BCP-47 short code, e.g. "es", "fr-CA".'
    )
    value = models.TextField()
    is_machine_translated = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('content_type', 'object_id', 'field', 'language_code')
        indexes = [
            models.Index(fields=['content_type', 'object_id', 'language_code']),
            models.Index(fields=['language_code', 'field']),
        ]

    def __str__(self) -> str:
        return f'{self.content_type.model}/{self.object_id}/{self.field}@{self.language_code}'
