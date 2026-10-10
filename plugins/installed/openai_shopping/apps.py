from django.apps import AppConfig


class OpenAIShoppingConfig(AppConfig):
    name = 'plugins.installed.openai_shopping'
    label = 'openai_shopping'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'ChatGPT Shopping feed'
