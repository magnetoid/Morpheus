from django.apps import AppConfig


class AgenticCheckoutConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.agentic_checkout'
    label = 'agentic_checkout'
    verbose_name = 'Agentic Commerce Protocol (ACP)'
