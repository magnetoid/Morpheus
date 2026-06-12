from django.apps import AppConfig


class UgcReviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.ugc_reviews'
    label = 'ugc_reviews'
    verbose_name = 'UGC reviews + creator program'
