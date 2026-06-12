from django.apps import AppConfig


class ReturnsPortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.returns_portal'
    label = 'returns_portal'
    verbose_name = 'Returns portal (retention surface)'
