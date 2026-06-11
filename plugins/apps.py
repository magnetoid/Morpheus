from django.apps import AppConfig


class PluginsConfig(AppConfig):
    name = 'plugins'

    def ready(self):
        from plugins.registry import plugin_registry

        plugin_registry.activate_all()

        # Populate plugin URLs after all plugins are active
        import plugins.urls

        plugins.urls.urlpatterns.clear()
        plugins.urls.urlpatterns.extend(plugin_registry.get_urlpatterns())
