from django.apps import AppConfig


class MotionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.motion'
    label = 'motion'
    verbose_name = 'Motion + skeleton states'
