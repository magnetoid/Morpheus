from django.apps import AppConfig


class PluginsConfig(AppConfig):
    name = 'plugins'

    def ready(self):
        from plugins.registry import app_registry

        app_registry.activate_all()

        # Populate plugin URLs after all plugins are active
        import plugins.urls

        plugins.urls.urlpatterns.clear()
        plugins.urls.urlpatterns.extend(app_registry.get_urlpatterns())
