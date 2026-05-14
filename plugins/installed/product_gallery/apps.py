from django.apps import AppConfig


class ProductGalleryConfig(AppConfig):
    name = 'plugins.installed.product_gallery'
    label = 'product_gallery'
    verbose_name = 'Product gallery'
    default_auto_field = 'django.db.models.BigAutoField'
