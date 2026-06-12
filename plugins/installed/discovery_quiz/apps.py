from django.apps import AppConfig


class DiscoveryQuizConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.discovery_quiz'
    label = 'discovery_quiz'
    verbose_name = 'Discovery quiz funnel'
