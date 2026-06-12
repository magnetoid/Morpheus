from django.apps import AppConfig


class SmartShippingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.smart_shipping'
    label = 'smart_shipping'
    verbose_name = 'Smart shipping + carbon display'
