from django.apps import AppConfig


class OrdersConfig(AppConfig):
    name = 'plugins.installed.orders'
    label = 'orders'
    verbose_name = 'Orders'

    def ready(self):
        from plugins.installed.orders.app import OrdersPlugin
        from plugins.registry import app_registry

        if 'orders' not in app_registry._classes:
            app_registry._classes['orders'] = OrdersPlugin
