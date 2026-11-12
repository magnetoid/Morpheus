"""plugins 0007 moves the channels' "Default brand" onto catalog (v0.163.0)."""

from __future__ import annotations

import importlib

from django.apps import apps
from django.test import TestCase

from plugins.models import PluginConfig

copy_default_brand = importlib.import_module(
    'plugins.migrations.0007_move_default_brand'
).copy_default_brand


def _row(name, **config):
    row, _ = PluginConfig.objects.get_or_create(plugin_name=name)
    row.config = {**(row.config or {}), **config}
    row.save()
    return row


def _catalog_brand():
    row = PluginConfig.objects.filter(plugin_name='catalog').first()
    return (row.config or {}).get('default_brand') if row else None


class MoveDefaultBrandTests(TestCase):
    def setUp(self):
        PluginConfig.objects.filter(plugin_name='catalog').update(config={})

    def test_google_shoppings_brand_is_copied(self):
        _row('google_shopping', default_brand=' Dot Books ')
        _row('meta_commerce', default_brand='Other')
        copy_default_brand(apps, None)
        self.assertEqual(_catalog_brand(), 'Dot Books')
        # The channel keeps its row for the release before.
        self.assertEqual(
            PluginConfig.objects.get(plugin_name='google_shopping').config['default_brand'],
            ' Dot Books ',
        )

    def test_another_channel_when_google_has_none(self):
        _row('google_shopping', default_brand='')
        _row('pinterest_commerce', default_brand='Pins Co')
        copy_default_brand(apps, None)
        self.assertEqual(_catalog_brand(), 'Pins Co')

    def test_catalogs_own_value_is_kept(self):
        _row('catalog', default_brand='Mine')
        _row('google_shopping', default_brand='Theirs')
        copy_default_brand(apps, None)
        self.assertEqual(_catalog_brand(), 'Mine')

    def test_nothing_to_copy_writes_nothing(self):
        copy_default_brand(apps, None)
        self.assertFalse(_catalog_brand())
