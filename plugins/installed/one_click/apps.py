from django.apps import AppConfig


class OneClickConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.one_click'
    label = 'one_click'
    verbose_name = 'One-click returning shopper'
