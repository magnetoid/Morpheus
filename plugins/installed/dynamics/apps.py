from django.apps import AppConfig


class DynamicsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.dynamics'
    # The Python module was renamed dynamic_products → dynamics, but the Django
    # app LABEL stays 'dynamic_products' on purpose: it keeps the existing DB
    # tables (dynamic_products_*), migration history, and content-types intact,
    # so the rename ships with zero data migration and zero prod risk.
    label = 'dynamic_products'

    def ready(self) -> None:
        # Import side-effect-free; the plugin manifest does the wiring.
        # Kept for parity with the plugin contract (signal/hook wiring
        # would land here if it weren't already handled in plugin.ready()).
        pass
