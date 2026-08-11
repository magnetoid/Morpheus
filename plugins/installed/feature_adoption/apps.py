from django.apps import AppConfig


class FeatureAdoptionConfig(AppConfig):
    name = 'plugins.installed.feature_adoption'
    label = 'feature_adoption'
    verbose_name = 'Feature adoption'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self) -> None:
        from plugins.installed.feature_adoption.app import FeatureAdoptionPlugin
        from plugins.registry import app_registry

        if 'feature_adoption' not in app_registry._classes:
            app_registry._classes['feature_adoption'] = FeatureAdoptionPlugin


default_app_config = 'plugins.installed.feature_adoption.apps.FeatureAdoptionConfig'
