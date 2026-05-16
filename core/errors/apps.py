from django.apps import AppConfig


class ErrorsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.errors'
    label = 'morph_errors'
    verbose_name = 'Morpheus error log'
