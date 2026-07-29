"""Agent write-tool contribution for the catalog plugin.

``products.update_status`` / ``products.update_price`` were migrated here from
core/assistant/tools/ecommerce_writes.py (core→plugin boundary refactor,
Phase 2). These tests lock the migration: both tools surface to the registry,
Linda, and the Worker with their approval/staging flags intact — and the
``pricing_change`` staging blocklist still fires (the behavioral test for that
lives in core/assistant/tests/test_staged_writes.py, which now imports the
plugin tool).
"""

from __future__ import annotations

from django.test import TestCase

from morpheus.core import agent_registry

_MIGRATED = ('products.update_status', 'products.update_price')


class CatalogAgentWriteToolTests(TestCase):
    def test_migrated_tools_registered_and_owned_by_catalog(self):
        for name in _MIGRATED:
            t = agent_registry.get_tool(name)
            self.assertIsNotNone(t, f'{name} not registered')
            self.assertEqual(t.plugin, 'catalog', f'{name} owned by {t.plugin!r}, expected catalog')

    def test_surfaced_to_linda_by_name(self):
        from core.assistant.tools import get_default_tools

        names = {t.name for t in get_default_tools()}
        for name in _MIGRATED:
            self.assertIn(name, names, f'{name} missing from Linda catalogue (_migrated_names)')

    def test_surfaced_to_worker_via_scope(self):
        worker = agent_registry.get_agent('worker')
        names = {t.name for t in worker.get_tools()}
        for name in _MIGRATED:
            self.assertIn(name, names, f'{name} not resolvable by the Worker')

    def test_flags_preserved(self):
        for name in _MIGRATED:
            t = agent_registry.get_tool(name)
            self.assertTrue(t.requires_approval, f'{name} lost requires_approval')
            self.assertTrue(t.supports_staging, f'{name} lost supports_staging')
