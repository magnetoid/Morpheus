from django.apps import AppConfig


class RichPostPurchaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.rich_post_purchase'
    label = 'rich_post_purchase'
    verbose_name = 'Rich post-purchase (multichannel)'
