from django.apps import AppConfig


class SubscriptionsPlusConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.subscriptions_plus'
    label = 'subscriptions_plus'
    verbose_name = 'Subscriptions / Replenish'
