"""Environment promotion tests."""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.environments.models import (
    Environment,
)
from plugins.installed.environments.services import promote, take_snapshot


class EnvironmentPromotionTests(TestCase):
    def setUp(self) -> None:
        self.dev = Environment.objects.create(
            name='Development',
            slug='dev',
            kind='development',
            theme_overrides={'theme': 'aurora-draft'},
            settings_overrides={'banner': 'beta'},
        )
        self.prod = Environment.objects.create(
            name='Production',
            slug='prod',
            kind='production',
            is_protected=True,
        )

    def test_take_snapshot_captures_overrides(self):
        snap = take_snapshot(self.dev, label='v1')
        self.assertEqual(snap.payload['theme_overrides'], {'theme': 'aurora-draft'})
        self.assertEqual(snap.payload['settings_overrides'], {'banner': 'beta'})

    def test_protected_target_requires_confirm(self):
        snap = take_snapshot(self.dev)
        with self.assertRaises(PermissionError):
            promote(snapshot=snap, target=self.prod)

    def test_promote_applies_payload_to_target(self):
        snap = take_snapshot(self.dev)
        deployment = promote(snapshot=snap, target=self.prod, confirm=True, note='ship it')
        self.prod.refresh_from_db()
        self.assertEqual(self.prod.theme_overrides, {'theme': 'aurora-draft'})
        self.assertEqual(deployment.status, 'applied')
        self.assertIn('changed', deployment.diff)
