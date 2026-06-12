from django.apps import AppConfig


class SaveForLaterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.save_for_later'
    label = 'save_for_later'
    verbose_name = 'Save for later'
