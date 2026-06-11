"""
Morpheus CMS — Plugin Models
PluginConfig: DB-backed per-plugin settings and activation status.
"""

import uuid

from django.db import models


class PluginConfig(models.Model):
    """
    One row per plugin. Stores:
    - Whether the plugin is behaviorally active (Tier 2 activation)
    - Plugin-specific configuration (rendered from plugin.get_config_schema())
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plugin_name = models.CharField(max_length=100, unique=True, db_index=True)
    is_enabled = models.BooleanField(default=True)
    config = models.JSONField(default=dict)
    installed_version = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plugin Config'
        verbose_name_plural = 'Plugin Configs'
        ordering = ['plugin_name']

    def __str__(self):
        status = 'enabled' if self.is_enabled else 'disabled'
        return f'{self.plugin_name} ({status})'
