from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    name = 'plugins.installed.analytics'
    label = 'analytics'
    verbose_name = 'Analytics'

    def ready(self):
        from plugins.installed.analytics.app import AnalyticsPlugin
        from plugins.registry import app_registry

        if 'analytics' not in app_registry._classes:
            app_registry._classes['analytics'] = AnalyticsPlugin


default_app_config = 'plugins.installed.analytics.apps.AnalyticsConfig'
