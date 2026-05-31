"""AppConfig for the self-improvement engine.

Wires hook subscribers in `ready()`. The engine is core-positioned and
always-on; there is no enable flag. What's configurable is the
per-class policy matrix in ``settings.SELF_IMPROVEMENT``.

Celery Beat schedule registration happens in `core/self_improvement/tasks.py`
which is auto-imported by Celery's task discovery.
"""

from __future__ import annotations

import logging

from django.apps import AppConfig

logger = logging.getLogger('morpheus.self_improvement')


class SelfImprovementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.self_improvement'
    label = 'morph_self_improvement'
    verbose_name = 'Morpheus self-improvement engine'

    def ready(self) -> None:
        # Wire push-driven collectors to their hook events. Subscribe by
        # priority 80 so we run before lower-priority listeners but
        # after critical ones (cart_abandonment recovery, etc.).
        try:
            self._register_subscribers()
        except Exception:  # noqa: BLE001 — engine boot must never break app boot
            logger.exception('self_improvement: subscriber registration failed')

    def _register_subscribers(self) -> None:
        # Lazy imports — apps may not yet be ready at the top of this
        # module, but they are by the time ready() fires.
        from core.hooks import MorpheusEvents, hook_registry  # noqa: PLC0415
        from core.self_improvement.collectors.cart_abandon import (  # noqa: PLC0415
            on_cart_abandoned,
        )
        from core.self_improvement.collectors.csp import (  # noqa: PLC0415
            on_csp_violation_reported,
        )
        from core.self_improvement.collectors.zero_search import (  # noqa: PLC0415
            on_search_performed,
        )

        hook_registry.register(MorpheusEvents.CART_ABANDONED, on_cart_abandoned, priority=80)
        hook_registry.register(MorpheusEvents.SEARCH_PERFORMED, on_search_performed, priority=80)
        hook_registry.register(
            MorpheusEvents.CSP_VIOLATION_REPORTED, on_csp_violation_reported, priority=80
        )

        logger.info('self_improvement: 3 hook subscribers registered')
