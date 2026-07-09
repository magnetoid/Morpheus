from django.apps import AppConfig


class LiveCommerceConfig(AppConfig):
    name = 'plugins.installed.live_commerce'
    label = 'live_commerce'
    verbose_name = 'Live commerce'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self) -> None:
        from plugins.installed.live_commerce.plugin import LiveCommercePlugin
        from plugins.registry import plugin_registry

        if 'live_commerce' not in plugin_registry._classes:
            plugin_registry._classes['live_commerce'] = LiveCommercePlugin


default_app_config = 'plugins.installed.live_commerce.apps.LiveCommerceConfig'
