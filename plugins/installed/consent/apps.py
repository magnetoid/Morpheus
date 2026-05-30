from django.apps import AppConfig


class ConsentConfig(AppConfig):
    name = 'plugins.installed.consent'
    label = 'consent'
    verbose_name = 'Cookie Consent'
    default_auto_field = 'django.db.models.BigAutoField'
