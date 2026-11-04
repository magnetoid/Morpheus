from django.apps import AppConfig


class ProductSafetyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.product_safety'
    label = 'product_safety'
    verbose_name = 'Product safety'
