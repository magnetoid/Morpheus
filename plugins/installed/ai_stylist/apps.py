from django.apps import AppConfig


class AiStylistConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.ai_stylist'
    label = 'ai_stylist'
    verbose_name = 'On-site AI stylist'
