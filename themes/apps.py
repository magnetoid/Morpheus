from django.apps import AppConfig


class ThemesConfig(AppConfig):
    name = 'themes'

    def ready(self) -> None:
        from django.conf import settings

        from themes.registry import theme_registry

        theme_registry.discover(settings.MORPHEUS_THEMES_DIR)
        theme_registry.set_active(settings.MORPHEUS_ACTIVE_THEME)
