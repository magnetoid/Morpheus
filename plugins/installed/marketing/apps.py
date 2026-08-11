from django.apps import AppConfig


class MarketingConfig(AppConfig):
    name = 'plugins.installed.marketing'
    label = 'marketing'
    verbose_name = 'Marketing'

    def ready(self):
        from plugins.installed.marketing.app import MarketingPlugin
        from plugins.registry import app_registry

        if 'marketing' not in app_registry._classes:
            app_registry._classes['marketing'] = MarketingPlugin


default_app_config = 'plugins.installed.marketing.apps.MarketingConfig'
