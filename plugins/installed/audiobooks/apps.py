# ready() uses lazy imports to avoid an app-loading import cycle (the established
# plugin pattern, cf. inventory/apps.py).
# ruff: noqa: PLC0415, I001
from django.apps import AppConfig


class AudiobooksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.audiobooks'
    label = 'audiobooks'
    verbose_name = 'Audiobooks'

    def ready(self):
        from plugins.registry import app_registry
        from plugins.installed.audiobooks.app import AudiobooksPlugin

        if 'audiobooks' not in app_registry._classes:
            app_registry._classes['audiobooks'] = AudiobooksPlugin


default_app_config = 'plugins.installed.audiobooks.apps.AudiobooksConfig'
