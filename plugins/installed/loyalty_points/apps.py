from django.apps import AppConfig


class LoyaltyPointsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.loyalty_points'
    label = 'loyalty_points'
    verbose_name = 'Loyalty points'

    def ready(self) -> None:
        # Subscribe earn-on-purchase handler at module-import time so the
        # listener is in place before any ORDER_PAID fire.
        from plugins.installed.loyalty_points import services  # noqa: F401, PLC0415

        services.register_handlers()

        # v1.1.0 — referral qualification on first qualifying order.
        try:
            from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415
            from plugins.installed.loyalty_points.handlers import (  # noqa: PLC0415
                on_order_placed_for_referrals,
            )

            hook_registry.register(
                MorpheusEvents.ORDER_PLACED,
                on_order_placed_for_referrals,
                priority=65,
            )
        except Exception:  # noqa: BLE001
            import logging  # noqa: PLC0415

            logging.getLogger('morpheus.loyalty.apps').exception(
                'loyalty: referral hook wiring failed'
            )
