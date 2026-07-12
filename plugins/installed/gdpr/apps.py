from django.apps import AppConfig


class GdprConfig(AppConfig):
    name = 'plugins.installed.gdpr'
    label = 'gdpr'
    verbose_name = 'GDPR / Privacy'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self) -> None:
        from plugins.installed.gdpr.plugin import GdprPlugin
        from plugins.registry import plugin_registry

        if 'gdpr' not in plugin_registry._classes:
            plugin_registry._classes['gdpr'] = GdprPlugin
