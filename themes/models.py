"""
Morpheus CMS — Theme Models
"""

import uuid

from django.db import models


class ThemeConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    theme_name = models.CharField(max_length=100, unique=True, db_index=True)
    is_active = models.BooleanField(default=False)
    config = models.JSONField(default=dict)  # theme customisation values
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Theme Config'
        verbose_name_plural = 'Theme Configs'

    def __str__(self):
        return f'{self.theme_name} ({"active" if self.is_active else "inactive"})'

    def save(self, *args, **kwargs):
        if self.is_active:
            # Only one theme active at a time
            ThemeConfig.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
