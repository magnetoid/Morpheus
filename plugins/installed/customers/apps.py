from django.apps import AppConfig


class CustomersConfig(AppConfig):
    name = 'plugins.installed.customers'
    label = 'customers'
    verbose_name = 'Customers'

    def ready(self):
        from plugins.installed.customers.app import CustomersPlugin
        from plugins.registry import app_registry

        if 'customers' not in app_registry._classes:
            app_registry._classes['customers'] = CustomersPlugin
