# ruff: noqa: PLC0415, F401, I001
from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = 'plugins.installed.catalog'
    label = 'catalog'
    verbose_name = 'Catalog'

    def ready(self):
        from plugins.registry import app_registry
        from plugins.installed.catalog.app import CatalogPlugin
        import plugins.installed.catalog.signals

        if 'catalog' not in app_registry._classes:
            app_registry._classes['catalog'] = CatalogPlugin

        # Typesense index sync (sprint priority #3). The hook subscribers
        # dispatch upserts via Celery; only active when settings.TYPESENSE
        # is configured. Falls back silently otherwise.
        try:
            from morpheus.core import MorpheusEvents, hook_registry
            from plugins.installed.catalog.search.handlers import (
                on_product_created,
                on_product_updated,
            )

            hook_registry.register(MorpheusEvents.PRODUCT_CREATED, on_product_created, priority=70)
            hook_registry.register(MorpheusEvents.PRODUCT_UPDATED, on_product_updated, priority=70)
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger('morpheus.catalog.search').exception(
                'catalog.search: hook wiring failed'
            )
