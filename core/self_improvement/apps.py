"""AppConfig for the self-improvement engine.

Wires hook subscribers + Celery Beat tasks in `ready()`. Per the v2 plan,
the engine is core-positioned and always-on; there is no enable flag.
What's configurable is the per-class policy matrix in
``settings.SELF_IMPROVEMENT``.
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
        # Subscribers + beat registration land in Increments 3-4. The
        # AppConfig must exist now (for migrations to be discovered)
        # but stays a no-op until those increments wire it up.
        logger.debug('self_improvement: AppConfig ready (subscribers pending)')
