"""An update starts from a backup and runs alone (v0.200.0).

- When the backup taken first failed, the self-update noted it in the plan and
  went on to merge and migrate, so a bad migration had nothing to go back to.
  The per-app update had the same copy.
- Nothing stopped two applies at once on one install.
- ``pg_dump`` and ``psql`` were started without the TLS settings Django itself
  connects with, so they fell back to libpq's ``prefer``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from core import component_updates, updates
from core.restore import pg_connection

STATUS_BEHIND = {
    'source': 'git',
    'available': 'yes',
    'upstream': 'origin/main',
    'current': 'v0.2.11',
    'latest': 'v0.2.12',
    'behind': 1,
}


def _backup_fails(name, *args, **kwargs):
    if name == 'morph_backup':
        raise CommandError('pg_dump is not installed')


@override_settings(MORPHEUS_SELF_UPDATE_ENABLED=True)
class PlatformApplyTests(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / '.git').mkdir()
        for target, value in (
            ('core.updates._repo_root', self.root),
            ('core.updates.platform_update_status', dict(STATUS_BEHIND)),
            ('core.updates._git', 'abc1234'),
            ('core.updates._dependency_changes', []),
        ):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        git_ok = patch('core.updates._git_ok', return_value=True)
        self.git_ok = git_ok.start()
        self.addCleanup(git_ok.stop)

    def _merged(self) -> bool:
        return any(call.args[0][:1] == ['merge'] for call in self.git_ok.call_args_list)

    def test_a_failed_backup_stops_the_update_before_anything_changes(self):
        with (
            patch('django.core.management.call_command', side_effect=_backup_fails) as cc,
            patch('core.updates._boot_probe') as probe,
        ):
            out = updates.apply_platform_update(confirm=True)

        self.assertEqual((out['ok'], out['status']), (False, 'backup_failed'))
        self.assertIn('pg_dump is not installed', out['reason'])
        self.assertFalse(self._merged())
        probe.assert_not_called()
        self.assertEqual([c.args[0] for c in cc.call_args_list], ['morph_backup'])

    def test_the_operator_can_update_without_a_backup_on_purpose(self):
        with (
            patch('django.core.management.call_command', side_effect=_backup_fails),
            patch('core.updates._boot_probe', return_value=(True, '')),
        ):
            out = updates.apply_platform_update(confirm=True, allow_without_backup=True)

        self.assertEqual(out['status'], 'applied')
        self.assertEqual(out['plan']['backup'], 'failed')
        self.assertTrue(self._merged())

    def test_a_second_apply_is_refused_while_one_runs(self):
        with (
            updates.apply_lock(self.root) as mine,
            patch('django.core.management.call_command') as cc,
        ):
            self.assertTrue(mine)
            out = updates.apply_platform_update(confirm=True)

        self.assertEqual((out['ok'], out['status']), (False, 'busy'))
        cc.assert_not_called()
        self.assertFalse(self._merged())

    def test_the_lock_is_free_again_after_an_apply(self):
        with (
            patch('django.core.management.call_command'),
            patch('core.updates._boot_probe', return_value=(True, '')),
        ):
            first = updates.apply_platform_update(confirm=True)
            second = updates.apply_platform_update(confirm=True)

        self.assertEqual((first['status'], second['status']), ('applied', 'applied'))

    def test_a_link_where_the_lock_file_goes_is_never_followed(self):
        import hashlib
        import os

        name = hashlib.sha256(str(self.root.resolve()).encode()).hexdigest()[:16]
        lock = Path(tempfile.gettempdir()) / f'morpheus-apply-{name}.lock'
        victim = self.root / 'someone-elses-file'
        victim.write_text('keep me')
        lock.unlink(missing_ok=True)
        os.symlink(victim, lock)
        self.addCleanup(lock.unlink, missing_ok=True)

        with patch('django.core.management.call_command') as cc:
            out = updates.apply_platform_update(confirm=True)

        self.assertEqual(out['status'], 'busy')
        self.assertEqual(victim.read_text(), 'keep me')
        cc.assert_not_called()

    def test_a_dry_run_needs_no_lock(self):
        with updates.apply_lock(self.root):
            out = updates.apply_platform_update(confirm=False)
        self.assertEqual(out['status'], 'dry_run')


class ComponentApplyLockTests(SimpleTestCase):
    def test_an_app_update_waits_for_the_platform_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with (
                patch('core.updates._repo_root', return_value=root),
                updates.apply_lock(root),
            ):
                out = component_updates.apply_component_update('app', 'whatever', confirm=True)
        self.assertEqual((out['ok'], out['status']), (False, 'busy'))


class PostgresClientEnvTests(SimpleTestCase):
    DB = {
        'HOST': 'db.internal',
        'PORT': 5433,
        'USER': 'shop',
        'PASSWORD': 'pw',
        'NAME': 'shop',
        'OPTIONS': {'sslmode': 'verify-full', 'sslrootcert': '/etc/ssl/ca.pem'},
    }

    def test_the_clients_get_the_tls_settings_django_uses(self):
        args, env = pg_connection(self.DB)
        self.assertEqual(args, ['-h', 'db.internal', '-p', '5433', '-U', 'shop'])
        self.assertEqual(env['PGSSLMODE'], 'verify-full')
        self.assertEqual(env['PGSSLROOTCERT'], '/etc/ssl/ca.pem')
        self.assertEqual(env['PGPASSWORD'], 'pw')

    def test_no_tls_setting_adds_none(self):
        with patch.dict('os.environ', {}, clear=True):
            _args, env = pg_connection({'HOST': 'db', 'OPTIONS': {}})
        self.assertNotIn('PGSSLMODE', env)

    def test_the_backup_dumps_with_them(self):
        from core.management.commands.morph_backup import Command

        db = {'ENGINE': 'django.db.backends.postgresql', **self.DB}
        with (
            tempfile.TemporaryDirectory() as tmp,
            override_settings(DATABASES={'default': db}),
            patch('subprocess.run') as run,
        ):
            Command()._dump_database(Path(tmp))

        cmd = run.call_args.args[0]
        self.assertEqual(cmd[0], 'pg_dump')
        self.assertEqual(cmd[-1], 'shop')
        self.assertIn('db.internal', cmd)
        self.assertEqual(run.call_args.kwargs['env']['PGSSLMODE'], 'verify-full')
