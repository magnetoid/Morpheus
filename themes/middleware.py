"""Theme middleware — sets active theme per request."""


class ThemeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self._theme_loaded = False

    def __call__(self, request):
        if not self._theme_loaded:
            try:
                from themes.registry import theme_registry

                theme_registry.set_active_from_db()
                self._theme_loaded = True
            except Exception:  # noqa: S110
                pass
        return self.get_response(request)
