"""Apps Wave 1: the ten apps that held no data and showed nothing are gone
(docs/plans/apps-consolidation-2026-10.md). Their tables outlive them by one release."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from plugins.registry import app_registry

REMOVED = (
    'one_click',
    'rich_post_purchase',
    'smart_shipping',
    'referrals',
    'experiments',
    'functions',
    'environments',
    'journal',
    'brand_kit',
    'lumina',
)


class RemovedAppsTests(SimpleTestCase):
    def test_the_removed_apps_are_not_installed(self):
        installed = set(settings.INSTALLED_APPS) | set(settings.MORPHEUS_DEFAULT_APPS)
        for name in REMOVED:
            self.assertNotIn(f'plugins.installed.{name}', installed)
            self.assertIsNone(app_registry.get(name), name)

    def test_their_code_is_gone(self):
        root = Path(settings.BASE_DIR) / 'plugins' / 'installed'
        left = [
            n for n in REMOVED if (root / n / 'apps.py').exists() or (root / n / 'app.py').exists()
        ]
        self.assertEqual(left, [])
