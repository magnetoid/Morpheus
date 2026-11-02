from __future__ import annotations

from django.apps import AppConfig


class PostPurchaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.post_purchase'
    label = 'post_purchase'
    verbose_name = 'Post-purchase journey'
