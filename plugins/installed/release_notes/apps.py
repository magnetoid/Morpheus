from django.apps import AppConfig


class ReleaseNotesConfig(AppConfig):
    name = 'plugins.installed.release_notes'
    label = 'release_notes'
    default_auto_field = 'django.db.models.BigAutoField'
