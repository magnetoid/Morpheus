"""Toggling an optional plugin off must never take the storefront down.

The disable litmus test (CLAUDE.md) says a disabled plugin's *surface*
disappears. There is a sharper failure mode underneath it: a shell or theme
that hard-references a plugin — `{% url 'seo:…' %}` in the theme `<head>` —
does not merely keep the surface, it **500s every page** the moment the plugin
is toggled off, because `deactivate()` unregisters the plugin's URLs and the
reverse fails inside the base template. The merchant sees "Turn off SEO" and
gets a dead storefront.

This test toggles each optional plugin the storefront/theme references and
asserts the storefront still answers. Extend `OPTIONAL` as sites are repaid.
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from plugins.registry import app_registry


class StorefrontSurvivesOptionalPluginDisableTests(TestCase):
    OPTIONAL = ('seo',)

    def setUp(self):
        cache.clear()  # a cached page fragment would hide a render failure

    def test_storefront_renders_with_each_optional_plugin_disabled(self):
        for name in self.OPTIONAL:
            with self.subTest(plugin=name):
                self.assertTrue(app_registry.is_active(name), f'{name} should start active')
                app_registry.deactivate(name)
                try:
                    cache.clear()
                    for path in ('/', '/products/'):
                        r = self.client.get(path)
                        self.assertEqual(
                            r.status_code,
                            200,
                            f'{path} returned {r.status_code} with {name} disabled',
                        )
                finally:
                    app_registry.activate(name)
                self.assertTrue(app_registry.is_active(name))
