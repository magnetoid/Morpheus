from django.apps import AppConfig


class LoyaltyPointsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.loyalty_points'
    label = 'loyalty_points'
    verbose_name = 'Loyalty points'
