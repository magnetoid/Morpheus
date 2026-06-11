from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    name = 'plugins.installed.analytics'
    label = 'analytics'
    verbose_name = 'Analytics'

    def ready(self):
        from plugins.installed.analytics.plugin import AnalyticsPlugin
        from plugins.registry import plugin_registry

        if 'analytics' not in plugin_registry._classes:
            plugin_registry._classes['analytics'] = AnalyticsPlugin


default_app_config = 'plugins.installed.analytics.apps.AnalyticsConfig'
