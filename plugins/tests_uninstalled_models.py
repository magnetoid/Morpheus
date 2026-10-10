"""A switched-off app's models never become part of the store's schema.

Supernatural Shop runs without the book vertical (MORPHEUS_DISABLED_APPS), so
`book_product` is not installed and its tables do not exist. Code elsewhere
still imports `plugins.installed.book_product.models` (catalog search,
sitemaps, feeds), and Django files a model whose own app is not installed
under the closest installed parent package: the `plugins` app. From then on
`catalog.Product` had a reverse relation to `plugins_bookproduct`, and every
product delete failed on that missing table (owner's report, 2026-10-11).
"""

from __future__ import annotations

from decimal import Decimal

from django.apps import apps
from django.db import models
from django.test import TestCase
from djmoney.money import Money


def _forget(model) -> None:
    apps.all_models['plugins'].pop(model._meta.model_name, None)
    apps.clear_cache()


class SwitchedOffAppModelTests(TestCase):
    def test_a_switched_off_apps_model_does_not_block_product_deletes(self):
        from plugins.installed.catalog.models import Product

        probe = type(
            'ZzSwitchedOffProbe',
            (models.Model,),
            {
                '__module__': 'plugins.installed.zz_switched_off_probe.models',
                'product': models.OneToOneField(
                    'catalog.Product', on_delete=models.CASCADE, related_name='zz_probe'
                ),
            },
        )
        self.addCleanup(_forget, probe)
        self.assertEqual(probe._meta.app_label, 'plugins')  # how Django files it

        product = Product.objects.create(
            name='Deletable', slug='deletable', sku='DEL-1', price=Money(Decimal('5'), 'USD')
        )
        product.delete()  # must not query the probe's (missing) table
        self.assertFalse(Product.objects.filter(slug='deletable').exists())

    def test_the_plugins_apps_own_models_are_still_listed(self):
        names = {m.__name__ for m in apps.get_app_config('plugins').get_models()}
        self.assertIn('PluginConfig', names)
