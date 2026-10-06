from django.apps import AppConfig


class DsersConfig(AppConfig):
    name = 'plugins.installed.dsers'
    label = 'dsers'
    verbose_name = 'DSers dropshipping'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self) -> None:
        from plugins.installed.dsers.app import DsersPlugin
        from plugins.registry import app_registry

        if 'dsers' not in app_registry._classes:
            app_registry._classes['dsers'] = DsersPlugin


default_app_config = 'plugins.installed.dsers.apps.DsersConfig'
