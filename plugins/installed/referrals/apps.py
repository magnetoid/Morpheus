from django.apps import AppConfig


class ReferralsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.referrals'
    label = 'referrals'
    verbose_name = 'Referrals — Give-5, Get-5'
