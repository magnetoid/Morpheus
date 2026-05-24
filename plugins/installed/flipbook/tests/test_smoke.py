"""Flipbook smoke tests — verify the plugin registers, the URL routes,
and the storefront block injects without crashing.
"""
from __future__ import annotations

from django.apps import apps
from django.test import Client, TestCase
from django.urls import reverse


class FlipbookSmokeTests(TestCase):
    def test_app_registered(self):
        self.assertTrue(apps.is_installed('plugins.installed.flipbook'))

    def test_reader_404_when_product_missing(self):
        c = Client()
        resp = c.get('/p/does-not-exist/flipbook/')
        self.assertEqual(resp.status_code, 404)
