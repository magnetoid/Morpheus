"""backups plugin smoke test."""
from __future__ import annotations

from django.test import TestCase


class BackupsSmokeTests(TestCase):
    def test_plugin_class_imports(self):
        from plugins.installed.backups.plugin import BackupsPlugin
        self.assertEqual(BackupsPlugin.name, "backups")
