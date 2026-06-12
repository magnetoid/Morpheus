from django.apps import AppConfig


class PostCheckoutUpsellConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.post_checkout_upsell'
    label = 'post_checkout_upsell'
    verbose_name = 'Post-checkout one-click upsell'
