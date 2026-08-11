"""digital_products plugin smoke test."""

from __future__ import annotations

from django.test import TestCase


class DigitalProductsSmokeTests(TestCase):
    def test_plugin_class_imports(self):
        from plugins.installed.digital_products.app import DigitalProductsPlugin

        self.assertEqual(DigitalProductsPlugin.name, 'digital_products')
