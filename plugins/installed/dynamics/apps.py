from django.apps import AppConfig


class DynamicProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.dynamic_products'
    label = 'dynamic_products'

    def ready(self) -> None:
        # Import side-effect-free; the plugin manifest does the wiring.
        # Kept for parity with the plugin contract (signal/hook wiring
        # would land here if it weren't already handled in plugin.ready()).
        pass
