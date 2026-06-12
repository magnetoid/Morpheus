from django.apps import AppConfig


class CheckoutExperienceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.checkout_experience'
    label = 'checkout_experience'
    verbose_name = 'Checkout experience'
