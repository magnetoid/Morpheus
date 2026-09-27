"""The nightly backup task honours the app's settings.

`run_backup` passed only `--no-media` to `morph_backup`, so the settings panel's
"Backup directory" and "Keep N most-recent backups" did nothing. Blank values
must still fall through to the command's own defaults — the worker's
persistent /app/backups volume and 7 copies.
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase

from plugins.installed.backups import tasks


def _run_with(config: dict) -> list:
    from plugins.registry import app_registry

    plugin = app_registry.get('backups')
    captured = {}

    def fake_call_command(name, *args, **kwargs):
        captured['args'] = list(args)
        kwargs['stdout'].write('ok\n')

    with (
        patch.object(plugin, 'get_config_value', side_effect=lambda k, d=None: config.get(k, d)),
        patch.object(tasks, 'call_command', side_effect=fake_call_command),
    ):
        tasks.run_backup.run()
    return captured['args']


class BackupTaskConfigTests(SimpleTestCase):
    def test_configured_directory_and_retention_reach_the_command(self):
        args = _run_with({'backup_dir': '/srv/backups', 'retention_count': 3})
        self.assertEqual(args[args.index('--dest') + 1], '/srv/backups')
        self.assertEqual(args[args.index('--keep') + 1], '3')

    def test_blank_settings_leave_the_command_defaults_alone(self):
        args = _run_with({'backup_dir': '', 'include_media': True})
        self.assertNotIn('--dest', args)
        self.assertNotIn('--keep', args)
        self.assertNotIn('--no-media', args)

    def test_the_panel_no_longer_defaults_to_an_ephemeral_directory(self):
        from plugins.registry import app_registry

        schema = app_registry.get('backups').get_config_schema()
        self.assertEqual(schema['properties']['backup_dir']['default'], '')
