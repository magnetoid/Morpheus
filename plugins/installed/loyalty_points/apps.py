from django.apps import AppConfig


class LoyaltyPointsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.loyalty_points'
    label = 'loyalty_points'
    verbose_name = 'Loyalty points'

    def ready(self) -> None:
        # Subscribe earn-on-purchase handler at module-import time so the
        # listener is in place before any ORDER_PAID fire.
        from plugins.installed.loyalty_points import services  # noqa: F401
        services.register_handlers()
