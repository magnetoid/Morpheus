from django.apps import AppConfig


class InventoryConfig(AppConfig):
    name = 'plugins.installed.inventory'
    label = 'inventory'
    verbose_name = 'Inventory'

    def ready(self):
        from plugins.installed.inventory.app import InventoryPlugin
        from plugins.registry import app_registry

        if 'inventory' not in app_registry._classes:
            app_registry._classes['inventory'] = InventoryPlugin


default_app_config = 'plugins.installed.inventory.apps.InventoryConfig'
