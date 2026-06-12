from django.apps import AppConfig


class BrandKitConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.brand_kit'
    label = 'brand_kit'
    verbose_name = 'Brand asset library + design tokens'
