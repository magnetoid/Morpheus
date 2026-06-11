from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        from core.utils.cache import SmartCacheInvalidator

        SmartCacheInvalidator.bind_events()

        # Transactional emails subscribe to domain events (ORDER_PLACED,
        # ORDER_PAID, etc.). Wired here so it runs once per process at
        # boot, not inside any one plugin's ready().
        from core.emails import register_handlers

        register_handlers()
