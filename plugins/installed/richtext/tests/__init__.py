"""richtext plugin — Lexical editor as a self-hosted app."""

from django.test import SimpleTestCase


class RichTextPluginContractTests(SimpleTestCase):
    def test_plugin_registered_and_active(self):
        from plugins.registry import plugin_registry

        self.assertTrue(plugin_registry.is_active('richtext'))
        plugin = plugin_registry.get('richtext')
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.name, 'richtext')
