from __future__ import annotations

import logging

from django.apps import AppConfig

logger = logging.getLogger('morpheus.fraud_rules')


class FraudRulesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.fraud_rules'
    label = 'fraud_rules'
    verbose_name = 'Fraud rules'

    def ready(self) -> None:
        try:
            from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415
            from plugins.installed.fraud_rules.handlers import on_order_placed  # noqa: PLC0415

            hook_registry.register(MorpheusEvents.ORDER_PLACED, on_order_placed, priority=85)
            logger.info('fraud_rules: ORDER_PLACED subscriber registered')
        except Exception:  # noqa: BLE001
            logger.exception('fraud_rules: subscriber wiring failed')
