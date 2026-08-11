def get_urlpatterns():
    from plugins.registry import app_registry

    return app_registry.get_urlpatterns()


urlpatterns = get_urlpatterns()
