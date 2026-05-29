from django.apps import AppConfig


class WebstoriesConfig(AppConfig):
    name = 'plugins.installed.webstories'
    label = 'webstories'
    verbose_name = 'Web Stories'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self) -> None:
        # Late import is required: AppConfig.ready() runs before all apps
        # are fully registered, so importing signals at module-load time
        # would break catalog/Product resolution. PLC0415 is the Django
        # canonical pattern for signal wiring.
        from plugins.installed.webstories import signals  # noqa: F401, PLC0415
