"""Personalisation plugin manifest."""

from __future__ import annotations

import logging

from morpheus import Plugin, StorefrontBlock, events

logger = logging.getLogger('morpheus.personalisation')


class PersonalisationPlugin(Plugin):
    name = 'personalisation'
    label = 'Personalisation'
    version = '1.1.0'
    description = (
        'Co-purchase recommendations on PDPs, plus per-visitor merchandising: '
        'reorders storefront product lists by purchase-propensity (embedding '
        'similarity to recently-viewed books + co-purchase). All consent-gated.'
    )

    def ready(self) -> None:
        # Subscribe to the PRODUCT_LIST_REORDER filter — when this plugin is
        # disabled the subscriber is gone and every list renders in its
        # original order, so personalisation vanishes with the toggle.
        self.register_hook(events.PRODUCT_LIST_REORDER, self._reorder_products, priority=50)
        # Nightly co-purchase recompute. The task existed but was never
        # scheduled, so CoPurchaseScore never refreshed (the docstring's
        # "runs nightly" was aspirational). 2:30am — ahead of the
        # dynamic_products propensity recompute (3:30am) that reads it.
        from celery.schedules import crontab  # noqa: PLC0415

        self.register_celery_tasks('plugins.installed.personalisation.tasks')
        self.register_celery_beat(
            'personalisation:recompute_copurchases',
            {
                'task': 'personalisation.recompute_copurchases',
                'schedule': crontab(hour=2, minute=30),
            },
        )

    def _reorder_products(self, value=None, request=None, surface: str = '', **kwargs):
        if value is None or request is None:
            return value
        try:
            from plugins.installed.personalisation.services import rank_for_visitor

            return rank_for_visitor(request, value, surface=surface)
        except Exception as e:  # noqa: BLE001 — never break a storefront render
            logger.warning('personalisation reorder failed (%s): %s', surface, e)
            return value

    def contribute_storefront_blocks(self) -> list[StorefrontBlock]:
        # The PDP "Pairs with this / Goes well together" block is retired per
        # merchant request (cropped book covers + only rendered for a few
        # products with co-purchase data). The recommendation services
        # (services.pairs_with) stay available for reuse; this just stops
        # contributing the storefront surface.
        return []
