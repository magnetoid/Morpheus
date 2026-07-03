from django.apps import AppConfig


class RichTextConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.richtext'
    label = 'richtext'
    verbose_name = 'Rich Text Editor (Lexical)'
