"""manage.py safe_migrate: a database backup before any migration (safe deploys, part 1).

The web container's entrypoint runs it in place of `migrate` on every boot
(scripts/docker-entrypoint.sh). Spec:
docs/superpowers/specs/2026-10-19-safe-deploys-design.md.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.test import SimpleTestCase, TestCase

from core import deploys
from core.management.commands.morph_backup import Command as BackupCommand
from core.management.commands.safe_migrate import Command as SafeMigrate

_REPO = Path(settings.BASE_DIR)


def _fake_dump(self, workdir):
    # The test database is in-memory SQLite, which morph_backup cannot copy. The
    # rest of the backup (archive, name, label, pruning) runs for real.
    (Path(workdir) / 'db.dump').write_bytes(b'dump')


def _broken_dump(self, workdir):
    raise subprocess.CalledProcessError(1, ['pg_dump'])


class _DeployEnvMixin:
    """A temporary backup folder and marker file, and a known commit."""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        env = {'MORPHEUS_BACKUP_DIR': str(self.root / 'backups'), 'SOURCE_COMMIT': 'a' * 40}
        for patcher in (
            patch.dict(os.environ, env),
            patch('core.deploys.HANDOFF', self.root / 'predeploy.json'),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def pend(self) -> str:
        """Mark core's newest migration unapplied, so `migrate` would run it.
        The test's transaction puts the row back."""
        leaf = next(
            name for app, name in MigrationLoader(connection).graph.leaf_nodes() if app == 'core'
        )
        MigrationRecorder(connection).record_unapplied('core', leaf)
        return f'core.{leaf}'

    def archives(self) -> list[str]:
        return sorted(p.name for p in (self.root / 'backups' / 'pre-deploy').glob('*.tar.gz'))


class MigrationPlanTests(_DeployEnvMixin, TestCase):
    def test_a_migrated_database_has_nothing_pending(self):
        self.assertEqual(deploys.migration_plan(), ([], False))

    def test_an_unapplied_migration_is_pending(self):
        name = self.pend()
        self.assertEqual(deploys.migration_plan(), ([name], False))


class SafeMigrateTests(_DeployEnvMixin, TestCase):
    def run_command(self, dump=_fake_dump, migrate=None):
        out = io.StringIO()
        with (
            patch.object(BackupCommand, '_dump_database', dump),
            patch.object(SafeMigrate, '_migrate', side_effect=migrate) as migrated,
        ):
            call_command('safe_migrate', stdout=out)
        return out.getvalue(), migrated

    def test_nothing_to_migrate_takes_no_backup(self):
        out, migrated = self.run_command()
        self.assertIn('No migrations to run', out)
        migrated.assert_called_once_with()
        self.assertEqual(self.archives(), [])

    def test_the_database_is_backed_up_before_migrating(self):
        self.pend()
        order = []

        def dump(command, workdir):
            order.append('backup')
            _fake_dump(command, workdir)

        self.run_command(dump=dump, migrate=lambda: order.append('migrate'))
        self.assertEqual(order, ['backup', 'migrate'])
        [archive] = self.archives()
        version = re.escape(settings.MORPHEUS_VERSION)
        self.assertRegex(archive, rf'^morpheus-backup-\d{{8}}T\d{{6}}Z-{version}-aaaaaaa\.tar\.gz$')
        with tarfile.open(self.root / 'backups' / 'pre-deploy' / archive) as tar:
            self.assertEqual(tar.getnames(), ['db.dump'])  # the database only, no media

    def test_the_last_five_are_kept_and_the_nightly_ones_untouched(self):
        folder = self.root / 'backups' / 'pre-deploy'
        folder.mkdir(parents=True)
        for day in range(1, 7):
            (folder / f'morpheus-backup-2020010{day}T000000Z-v0.1.{day}.tar.gz').write_bytes(b'o')
        nightly = self.root / 'backups' / 'morpheus-backup-20200101T000000Z.tar.gz'
        nightly.write_bytes(b'n')
        self.pend()
        self.run_command()
        names = self.archives()
        self.assertEqual(len(names), 5)
        self.assertNotIn('morpheus-backup-20200101T000000Z-v0.1.1.tar.gz', names)
        self.assertNotIn('morpheus-backup-20200102T000000Z-v0.1.2.tar.gz', names)
        self.assertTrue(nightly.exists())

    def test_a_failed_backup_stops_before_migrating_and_leaves_nothing(self):
        self.pend()
        with (
            patch.object(BackupCommand, '_dump_database', _broken_dump),
            patch.object(SafeMigrate, '_migrate') as migrated,
            self.assertRaises(CommandError) as raised,
        ):
            call_command('safe_migrate', stdout=io.StringIO())
        migrated.assert_not_called()
        self.assertIn('nothing was migrated', str(raised.exception))
        self.assertEqual(self.archives(), [])
        self.assertIsNone(deploys.read_handoff())

    def test_a_restart_after_a_failed_migrate_does_not_back_up_again(self):
        # A crash loop: the first boot backed up, then migrate failed, and the
        # container restarted with migrations still pending.
        self.pend()

        def boom():
            raise RuntimeError('migrate failed')

        with self.assertRaises(RuntimeError):
            self.run_command(migrate=boom)
        first = deploys.read_handoff()
        self.assertTrue(first['backup'])
        out, migrated = self.run_command()
        self.assertIn('not repeated', out)
        migrated.assert_called_once_with()
        self.assertEqual(len(self.archives()), 1)

    def test_a_new_database_has_nothing_to_back_up(self):
        MigrationRecorder(connection).migration_qs.all().delete()
        with patch('core.deploys.clear_handoff'):  # keep the marker to read it
            out, _ = self.run_command()
        self.assertIn('New database', out)
        self.assertEqual(self.archives(), [])
        marker = deploys.read_handoff()
        self.assertEqual(marker['backup'], '')
        self.assertIn('core.0001_initial', marker['migrations'])

    def test_a_successful_run_clears_the_marker(self):
        self.pend()
        self.run_command()
        self.assertIsNone(deploys.read_handoff())

    def test_migrate_runs_its_system_checks_without_prompts(self):
        # `manage.py migrate` ran the system checks at every boot, and they are what
        # stops a boot on a broken model relation; call_command skips them by default.
        with patch('core.management.commands.safe_migrate.call_command') as called:
            SafeMigrate()._migrate()
        called.assert_called_once_with('migrate', interactive=False, skip_checks=False)


class BackupArchiveTests(_DeployEnvMixin, TestCase):
    def backup(self, **options):
        dest = self.root / 'b'
        with patch.object(BackupCommand, '_dump_database', _fake_dump):
            call_command(
                'morph_backup', dest=str(dest), no_media=True, stdout=io.StringIO(), **options
            )
        return dest

    def test_a_backup_that_fails_while_writing_leaves_no_archive(self):
        # A full disk half way through: the partial file would look like a good
        # backup to whoever restores from it.
        full = OSError(28, 'No space left on device')
        with patch('tarfile.TarFile.add', side_effect=full), self.assertRaises(OSError):
            self.backup()
        self.assertEqual(list((self.root / 'b').glob('*')), [])

    def test_a_label_is_made_safe_for_a_file_name(self):
        [archive] = self.backup(label='v0.118.0 beta/2').glob('*.tar.gz')
        self.assertRegex(archive.name, r'^morpheus-backup-\d{8}T\d{6}Z-v0\.118\.0-beta-2\.tar\.gz$')

    def test_no_label_keeps_the_nightly_name(self):
        [archive] = self.backup().glob('*.tar.gz')
        self.assertRegex(archive.name, r'^morpheus-backup-\d{8}T\d{6}Z\.tar\.gz$')


class DeployWiringTests(SimpleTestCase):
    def test_the_web_container_keeps_its_backups_on_the_backup_volume(self):
        # PyYAML is not in the requirements: read the web service's block as text.
        text = (_REPO / 'docker-compose.yml').read_text()
        web = text[text.index('\n  web:\n') : text.index('\n  worker:\n')]
        self.assertIn('- backup_data:/app/backups', web)

    def boot(self, exit_code):
        """The entrypoint's web mode, with stand-in `python` and `gunicorn`."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        log = tmp / 'calls.log'
        for name, code in (('python', exit_code), ('gunicorn', 0)):
            fake = tmp / name
            fake.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\nexit {code}\n')
            fake.chmod(0o755)
        proc = subprocess.run(
            ['sh', str(_REPO / 'scripts' / 'docker-entrypoint.sh'), 'web'],
            env={'PATH': f'{tmp}{os.pathsep}{os.environ["PATH"]}'},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return proc.returncode, log.read_text().splitlines()

    def test_migrations_go_through_safe_migrate_before_gunicorn(self):
        code, calls = self.boot(exit_code=0)
        self.assertEqual(code, 0)
        self.assertEqual(calls[0], 'python manage.py safe_migrate')
        self.assertTrue(calls[1].startswith('gunicorn '), calls)

    def test_a_failed_backup_stops_the_boot(self):
        code, calls = self.boot(exit_code=1)
        self.assertNotEqual(code, 0)
        self.assertEqual(calls, ['python manage.py safe_migrate'])
