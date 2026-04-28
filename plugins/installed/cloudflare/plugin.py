"""Cloudflare plugin manifest."""
from __future__ import annotations

import logging

from morpheus import events
from morpheus import Plugin

logger = logging.getLogger('morpheus.cloudflare')


class CloudflarePlugin(Plugin):
    name = 'cloudflare'
    label = 'Cloudflare'
    version = '0.1.0'
    description = 'Cloudflare cache purge + DNS integration. Auto-purges on product/collection updates.'
    has_models = True

    def ready(self) -> None:
        self.register_graphql_extension('plugins.installed.cloudflare.graphql.queries')
        self.register_graphql_extension('plugins.installed.cloudflare.graphql.mutations')
        self.register_hook(events.PRODUCT_UPDATED, self.on_product_updated, priority=85)
        self.register_hook(events.PRODUCT_CREATED, self.on_product_updated, priority=85)
        self.register_hook(events.CATEGORY_UPDATED, self.on_category_updated, priority=85)

    def on_product_updated(self, product, **kwargs):
        try:
            from plugins.installed.cloudflare.services import purge_for_product_update
            purge_for_product_update(product)
        except Exception as e:  # noqa: BLE001 — log + swallow, never break order/catalog flow
            logger.warning('cloudflare: hook purge failed: %s', e, exc_info=True)

    def on_category_updated(self, category=None, **kwargs):
        if category is None:
            return
        try:
            from plugins.installed.cloudflare.models import CloudflareZone
            from plugins.installed.cloudflare.services import purge_urls

            qs = CloudflareZone.objects.filter(
                is_active=True, auto_purge_on_collection_update=True,
            ).select_related('account')
            for zone in qs:
                purge_urls(
                    zone=zone,
                    urls=[f'https://{zone.domain}/c/{getattr(category, "slug", "")}'],
                    triggered_by=f'category:{getattr(category, "id", "")}',
                )
        except Exception as e:  # noqa: BLE001
            logger.warning('cloudflare: category hook purge failed: %s', e, exc_info=True)
