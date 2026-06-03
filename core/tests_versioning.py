"""Contract test for the component version inventory (updating system P1)."""

from __future__ import annotations

from django.test import SimpleTestCase

from core.versioning import component_versions, core_version


class ComponentVersionsTests(SimpleTestCase):
    def test_core_version_present(self):
        self.assertTrue(core_version())

    def test_inventory_shape(self):
        data = component_versions()
        self.assertIn('core', data)
        self.assertIsInstance(data['plugins'], list)
        self.assertIsInstance(data['themes'], list)

    def test_plugins_enumerated_with_required_keys(self):
        plugins = component_versions()['plugins']
        self.assertTrue(plugins, 'expected registered plugins')
        for key in ('name', 'label', 'version', 'enabled'):
            self.assertIn(key, plugins[0])
        names = {p['name'] for p in plugins}
        self.assertIn('catalog', names)  # a core-ish plugin always present

    def test_theme_entries_well_formed(self):
        # Theme discovery runs at server startup, not under SimpleTestCase, so
        # the list may be empty here — just assert shape when present.
        for t in component_versions()['themes']:
            for key in ('name', 'version', 'active'):
                self.assertIn(key, t)
