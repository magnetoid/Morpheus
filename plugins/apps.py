from django.apps import AppConfig


class PluginsConfig(AppConfig):
    name = 'plugins'

    def get_models(self, include_auto_created=False, include_swapped=False):
        """The `plugins` package's own models, never an uninstalled app's.

        A store can switch an app off (MORPHEUS_DISABLED_APPS, or an opt-in app it
        never enabled). When code elsewhere still imports that app's models
        module, Django files each model under the closest installed parent
        package, which is this app, so a model like `BookProduct` turned up here
        with a OneToOne to `catalog.Product` and a table that does not exist on
        that store. Every product delete then failed on the missing table
        (supernatural, 2026-10-11). Leaving such models out of `get_models()`
        keeps them out of every model's relations, the delete collector and
        `makemigrations`, while an import of the module still works.
        """
        for model in super().get_models(include_auto_created, include_swapped):
            if model.__module__.startswith('plugins.installed.'):
                continue
            yield model

    def ready(self):
        from plugins.registry import app_registry

        app_registry.activate_all()

        # Populate plugin URLs after all plugins are active
        import plugins.urls

        plugins.urls.urlpatterns.clear()
        plugins.urls.urlpatterns.extend(app_registry.get_urlpatterns())
