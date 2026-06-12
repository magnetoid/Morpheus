from django.apps import AppConfig


class LookbookConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.lookbook'
    label = 'lookbook'
    verbose_name = 'Lookbook / Outfit builder'
