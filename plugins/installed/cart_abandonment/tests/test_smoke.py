"""cart_abandonment plugin smoke test."""

from __future__ import annotations

from django.test import TestCase


class CartAbandonmentSmokeTests(TestCase):
    def test_plugin_class_imports(self):
        from plugins.installed.cart_abandonment.app import CartAbandonmentPlugin

        self.assertEqual(CartAbandonmentPlugin.name, 'cart_abandonment')
