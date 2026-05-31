from __future__ import annotations

from django.apps import AppConfig


class PersonalisationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.personalisation'
    label = 'personalisation'
    verbose_name = 'Personalisation (co-purchase + recs)'
