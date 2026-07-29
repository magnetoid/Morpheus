from __future__ import annotations

import logging

from django.apps import AppConfig

logger = logging.getLogger('morpheus.post_purchase')


class PostPurchaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.post_purchase'
    label = 'post_purchase'
    verbose_name = 'Post-purchase journey'

    def ready(self) -> None:
        try:
            self._wire_hooks()
        except Exception:  # noqa: BLE001
            logger.exception('post_purchase: subscriber registration failed')

    def _wire_hooks(self) -> None:
        from morpheus.core import MorpheusEvents, hook_registry  # noqa: PLC0415
        from plugins.installed.post_purchase.handlers import (  # noqa: PLC0415
            on_order_fulfilled,
            on_order_placed,
        )

        hook_registry.register(MorpheusEvents.ORDER_PLACED, on_order_placed, priority=60)
        hook_registry.register(MorpheusEvents.ORDER_FULFILLED, on_order_fulfilled, priority=60)
        logger.info('post_purchase: 2 subscribers registered')
