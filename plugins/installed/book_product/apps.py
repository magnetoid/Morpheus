from django.apps import AppConfig


class BookProductConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'plugins.installed.book_product'
    label = 'book_product'

    def ready(self):
        # A deleted book takes its social card file with it. Wired here, not in
        # the app manifest's ready(): that runs only while the app is switched
        # on at start-up, and a book deleted while it is off is still deleted.
        from django.db.models.signals import post_delete

        from plugins.installed.book_product.models import BookProduct

        post_delete.connect(
            _delete_social_card, sender=BookProduct, dispatch_uid='book_product.social_card'
        )


def _delete_social_card(sender, instance, **kwargs):
    from plugins.installed.book_product.social_cards import delete_card_file

    delete_card_file(instance)
