from django.apps import AppConfig


class OrdersConfig(AppConfig):
    name = 'plugins.installed.orders'
    label = 'orders'
    verbose_name = 'Orders'

    def ready(self):
        from plugins.installed.orders.plugin import OrdersPlugin
        from plugins.registry import plugin_registry

        if 'orders' not in plugin_registry._classes:
            plugin_registry._classes['orders'] = OrdersPlugin
