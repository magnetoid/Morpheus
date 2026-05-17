from django.apps import AppConfig


class TrackingConfig(AppConfig):
    name = 'plugins.installed.tracking'
    label = 'tracking'
    default_auto_field = 'django.db.models.BigAutoField'
