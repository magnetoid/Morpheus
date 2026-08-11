from django.apps import AppConfig


class GdprConfig(AppConfig):
    name = 'plugins.installed.gdpr'
    label = 'gdpr'
    verbose_name = 'GDPR / Privacy'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self) -> None:
        from plugins.installed.gdpr.app import GdprPlugin
        from plugins.registry import app_registry

        if 'gdpr' not in app_registry._classes:
            app_registry._classes['gdpr'] = GdprPlugin
