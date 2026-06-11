def get_urlpatterns():
    from plugins.registry import plugin_registry

    return plugin_registry.get_urlpatterns()


urlpatterns = get_urlpatterns()
