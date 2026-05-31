from __future__ import annotations

from django.apps import AppConfig


class TrustSignalsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.trust_signals'
    label = 'trust_signals'
    verbose_name = 'Trust signals on PDP'
