from __future__ import annotations

from django.apps import AppConfig


class ExperimentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.experiments'
    label = 'experiments'
    verbose_name = 'A/B experiments'
