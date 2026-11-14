"""The payments card reaches every worker (v0.166.0 review).

A save clears only the process that made it. The card holds when cards are
charged and whether the cart offers express checkout, so payments sets
``config_fresh_s``: every web and Celery worker reads the card again once that
window passes, and the wallet sheet and the PaymentIntent agree.
"""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.payments import express
from plugins.installed.payments.services import capture
from plugins.models import PluginConfig
from plugins.registry import app_registry


class SettingsReachEveryWorkerTests(TestCase):
    def setUp(self):
        self.plugin = app_registry.get('payments')
        self.plugin.invalidate_config_cache()
        self.addCleanup(self.plugin.invalidate_config_cache)
        self.row, _ = PluginConfig.objects.get_or_create(plugin_name='payments')

    def _saved_in_another_worker(self, **values):
        # A queryset update: the row changes and this process's cache does not.
        config = {**(self.row.config or {}), **values}
        PluginConfig.objects.filter(pk=self.row.pk).update(config=config)

    def _window_passes(self):
        self.plugin._config_read_at -= self.plugin.config_fresh_s

    def test_when_cards_are_charged_reaches_this_worker_once_the_window_passes(self):
        self._saved_in_another_worker(capture_mode='immediate')
        self.assertEqual(capture._setting('capture_mode', ''), 'immediate')
        self._saved_in_another_worker(capture_mode='manual')
        self.assertEqual(capture._setting('capture_mode', ''), 'immediate')
        self._window_passes()
        self.assertEqual(capture._setting('capture_mode', ''), 'manual')

    def test_express_on_the_cart_reaches_this_worker_once_the_window_passes(self):
        self._saved_in_another_worker(express_on_cart=True)
        self.assertIs(express._setting('express_on_cart', None), True)
        self._saved_in_another_worker(express_on_cart=False)
        self._window_passes()
        self.assertIs(express._setting('express_on_cart', None), False)
