"""A/B experiments plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import Plugin

logger = logging.getLogger('morpheus.experiments.plugin')


class ExperimentsPlugin(Plugin):
    name = 'experiments'
    label = 'A/B experiments'
    version = '1.0.0'
    description = (
        'In-process A/B testing tied to the existing tracking hooks. '
        'Wald-interval significance; cookie-stable variant assignment.'
    )

    def ready(self) -> None:
        try:
            from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415
            from plugins.installed.experiments.handlers import (  # noqa: PLC0415
                on_order_placed,
                on_signup,
            )

            hook_registry.register(MorpheusEvents.ORDER_PLACED, on_order_placed, priority=70)
            hook_registry.register(MorpheusEvents.CUSTOMER_REGISTERED, on_signup, priority=70)
            logger.info('experiments: 2 conversion hooks registered')
        except Exception:  # noqa: BLE001
            logger.exception('experiments: hook wiring failed')
