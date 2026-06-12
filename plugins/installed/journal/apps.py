from django.apps import AppConfig


class JournalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.journal'
    label = 'journal'
    verbose_name = 'Journal — story-telling CMS'
