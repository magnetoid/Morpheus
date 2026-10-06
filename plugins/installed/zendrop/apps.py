from django.apps import AppConfig


class ZendropConfig(AppConfig):
    name = 'plugins.installed.zendrop'
    label = 'zendrop'
    verbose_name = 'Zendrop dropshipping'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self) -> None:
        from plugins.installed.zendrop.app import ZendropPlugin
        from plugins.registry import app_registry

        if 'zendrop' not in app_registry._classes:
            app_registry._classes['zendrop'] = ZendropPlugin


default_app_config = 'plugins.installed.zendrop.apps.ZendropConfig'
