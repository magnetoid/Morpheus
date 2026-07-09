from django.apps import AppConfig


class FeatureAdoptionConfig(AppConfig):
    name = 'plugins.installed.feature_adoption'
    label = 'feature_adoption'
    verbose_name = 'Feature adoption'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self) -> None:
        from plugins.installed.feature_adoption.plugin import FeatureAdoptionPlugin
        from plugins.registry import plugin_registry

        if 'feature_adoption' not in plugin_registry._classes:
            plugin_registry._classes['feature_adoption'] = FeatureAdoptionPlugin


default_app_config = 'plugins.installed.feature_adoption.apps.FeatureAdoptionConfig'
