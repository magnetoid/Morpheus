"""apply_platform_update crash-safety gates: dependency guard + fresh-interpreter
boot-probe (before migrate, so a non-bootable update reverts with DB untouched)."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings

from core import updates

STATUS_BEHIND = {
    'source': 'git',
    'available': 'yes',
    'upstream': 'origin/main',
    'current': 'v0.2.11',
    'latest': 'v0.2.12',
    'behind': 1,
}


@override_settings(MORPHEUS_SELF_UPDATE_ENABLED=True)
class ApplySafetyTests(TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        (root / '.git').mkdir()
        self.root = root
        self._stack = [
            patch('core.updates._repo_root', return_value=root),
            patch('core.updates.platform_update_status', return_value=dict(STATUS_BEHIND)),
            patch('core.updates._git', return_value='abc1234'),
            patch('core.updates._git_ok', return_value=True),
        ]
        for p in self._stack:
            p.start()

    def tearDown(self):
        for p in self._stack:
            p.stop()
        self._tmp.cleanup()

    def test_dependency_change_refuses_before_any_mutation(self):
        with (
            patch('core.updates._dependency_changes', return_value=['requirements.txt']),
            patch('django.core.management.call_command') as cc,
            patch('core.updates._boot_probe') as probe,
        ):
            out = updates.apply_platform_update(confirm=True)
        self.assertEqual(out['status'], 'deps_changed')
        self.assertFalse(out['ok'])
        self.assertIn('requirements.txt', out['plan']['dependency_files'])
        cc.assert_not_called()  # no backup / merge / migrate
        probe.assert_not_called()

    def test_dependency_change_allowed_proceeds(self):
        with (
            patch('core.updates._dependency_changes', return_value=['requirements.txt']),
            patch('django.core.management.call_command'),
            patch('core.updates._boot_probe', return_value=(True, '')),
        ):
            out = updates.apply_platform_update(confirm=True, allow_dependency_changes=True)
        self.assertEqual(out['status'], 'applied')

    def test_boot_probe_failure_rolls_back_before_migrate(self):
        with (
            patch('core.updates._dependency_changes', return_value=[]),
            patch(
                'core.updates._boot_probe', return_value=(False, 'ImportError: no module xmlsec')
            ),
            patch('django.core.management.call_command') as cc,
        ):
            out = updates.apply_platform_update(confirm=True)
        self.assertEqual(out['status'], 'rolled_back')
        self.assertIn('failed to boot', out['reason'])
        # backup ran, but migrate must NOT have (probe gate is before migrate)
        called = [c.args[0] for c in cc.call_args_list]
        self.assertIn('morph_backup', called)
        self.assertNotIn('migrate', called)

    def test_happy_path_applies(self):
        with (
            patch('core.updates._dependency_changes', return_value=[]),
            patch('core.updates._boot_probe', return_value=(True, '')),
            patch('django.core.management.call_command') as cc,
        ):
            out = updates.apply_platform_update(confirm=True)
        self.assertEqual(out['status'], 'applied')
        called = [c.args[0] for c in cc.call_args_list]
        self.assertIn('migrate', called)
        self.assertIn('check', called)
