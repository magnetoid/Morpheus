from django.apps import AppConfig


class CustomersConfig(AppConfig):
    name = 'plugins.installed.customers'
    label = 'customers'
    verbose_name = 'Customers'

    def ready(self):
        from plugins.installed.customers.plugin import CustomersPlugin
        from plugins.registry import plugin_registry

        if 'customers' not in plugin_registry._classes:
            plugin_registry._classes['customers'] = CustomersPlugin
