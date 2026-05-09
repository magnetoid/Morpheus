from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.reviews'
    label = 'reviews'
    verbose_name = 'Reviews'
