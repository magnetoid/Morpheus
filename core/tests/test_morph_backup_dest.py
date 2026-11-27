"""manage.py morph_backup: never into a folder the web server serves, and never an
archive without its database."""

from __future__ import annotations

import contextlib
import io
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from core.management.commands.morph_backup import Command as BackupCommand
from core.tests.test_safe_migrate import _fake_dump


class _Tmp:
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        (self.root / 'media').mkdir()
        (self.root / 'static').mkdir()

    def backup(self, dest):
        with patch.object(BackupCommand, '_dump_database', _fake_dump):
            call_command('morph_backup', dest=str(dest), no_media=True, stdout=io.StringIO())


class ServedFolderTests(_Tmp, SimpleTestCase):
    """The backups app passes its staff-editable folder as --dest, and MEDIA_ROOT
    is served to anyone: a dump there is public."""

    def setUp(self):
        super().setUp()
        roots = override_settings(MEDIA_ROOT=self.root / 'media', STATIC_ROOT=self.root / 'static')
        roots.enable()
        self.addCleanup(roots.disable)

    def assert_refused(self, dest, created):
        with self.assertRaisesMessage(CommandError, 'served to anyone'):
            self.backup(dest)
        self.assertFalse(created.exists())

    def test_a_folder_inside_media_is_refused(self):
        self.assert_refused(self.root / 'media' / 'backups', self.root / 'media' / 'backups')

    def test_the_media_folder_itself_is_refused(self):
        self.assert_refused(self.root / 'media', self.root / 'media' / 'nothing')

    def test_a_link_into_media_is_refused(self):
        (self.root / 'link').symlink_to(self.root / 'media')
        self.assert_refused(self.root / 'link' / 'backups', self.root / 'media' / 'backups')

    def test_a_relative_path_into_static_is_refused(self):
        with contextlib.chdir(self.root / 'media'):
            self.assert_refused('../static/backups', self.root / 'static' / 'backups')

    def test_a_folder_outside_both_is_fine(self):
        self.backup(self.root / 'backups')
        self.assertEqual(len(list((self.root / 'backups').glob('morpheus-backup-*.tar.gz'))), 1)


class EngineTests(_Tmp, SimpleTestCase):
    """A backup without its database must fail: safe_migrate migrates behind it."""

    def settings_with(self, engine):
        db = {'ENGINE': engine, 'NAME': 'shop', 'HOST': 'db'}
        fake = SimpleNamespace(DATABASES={'default': db}, MEDIA_ROOT='', STATIC_ROOT='')
        return patch('core.management.commands.morph_backup.settings', fake)

    def test_postgis_is_dumped_like_postgres(self):
        with (
            self.settings_with('django.contrib.gis.db.backends.postgis'),
            patch('core.management.commands.morph_backup.subprocess.run') as run,
        ):
            BackupCommand(stdout=io.StringIO())._dump_database(self.root)
        self.assertEqual(run.call_args.args[0][0], 'pg_dump')
        self.assertEqual(run.call_args.args[0][-1], 'shop')

    def test_an_engine_it_cannot_dump_fails_and_writes_no_archive(self):
        dest = self.root / 'backups'
        with (
            self.settings_with('django.db.backends.mysql'),
            self.assertRaisesMessage(CommandError, 'django.db.backends.mysql'),
        ):
            call_command('morph_backup', dest=str(dest), no_media=True, stdout=io.StringIO())
        self.assertEqual(list(dest.glob('*')), [])
