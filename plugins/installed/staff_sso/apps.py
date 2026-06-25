from django.apps import AppConfig


class StaffSsoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.staff_sso'
    label = 'staff_sso'
    verbose_name = 'Staff SSO (OIDC)'
