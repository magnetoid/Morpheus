"""manage.py morph_restore: all or nothing, the current data saved first (safe deploys, part 4)."""

from __future__ import annotations

import contextlib
import io
import os
import signal
import sqlite3
import subprocess
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase

from core import deploys, restore
from core.models import StoreSettings

NAME = 'morpheus-backup-20261020T012146Z-v0.118.0-e1198af.tar.gz'
BEFORE = 'morpheus-backup-20261020T170000Z-before-restore.tar.gz'


def _archive(folder: Path, name: str = NAME, members: dict | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    with tarfile.open(path, 'w:gz') as tar:
        for member, data in (members if members is not None else {'db.dump': b'DUMP'}).items():
            info = tarfile.TarInfo(member)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


class _Folder:
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        env = patch.dict(os.environ, {'MORPHEUS_BACKUP_DIR': tmp.name})
        env.start()
        self.addCleanup(env.stop)


class DescribeBackupTests(_Folder, SimpleTestCase):
    def test_a_backup_is_described_by_its_name_and_size(self):
        path = _archive(self.root)
        info = deploys.describe_backup(path)
        self.assertEqual(info['label'], 'v0.118.0-e1198af')
        self.assertEqual(info['taken_at'].isoformat(), '2026-10-20T01:21:46+00:00')
        self.assertEqual(info['size'], path.stat().st_size)

    def test_a_name_with_an_impossible_date_is_skipped(self):
        path = self.root / 'morpheus-backup-20261399T999999Z.tar.gz'
        path.write_bytes(b'x')
        self.assertIsNone(deploys.describe_backup(path))

    def test_an_unfinished_backup_is_skipped(self):
        path = self.root / f'{NAME}.part'
        path.write_bytes(b'x')
        self.assertIsNone(deploys.describe_backup(path))


class ExtractTests(_Folder, SimpleTestCase):
    def test_the_dump_comes_out_of_the_archive(self):
        into = self.root / 'out'
        into.mkdir()
        dump = restore.extract_dump(_archive(self.root), into)
        self.assertEqual(dump.read_bytes(), b'DUMP')

    def test_an_archive_without_a_database_is_refused(self):
        with self.assertRaisesMessage(restore.RestoreError, 'holds no database'):
            restore.extract_dump(_archive(self.root, members={'media.tar': b'm'}), self.root)

    def test_a_file_that_is_not_an_archive_is_refused(self):
        junk = self.root / NAME
        junk.write_bytes(b'not a tar')
        with self.assertRaisesMessage(restore.RestoreError, 'cannot be read'):
            restore.extract_dump(junk, self.root)

    def test_a_dump_that_is_a_link_is_refused(self):
        path = self.root / NAME
        with tarfile.open(path, 'w:gz') as tar:
            link = tarfile.TarInfo('db.dump')
            link.type = tarfile.SYMTYPE
            link.linkname = '/etc/passwd'
            tar.addfile(link)
        with self.assertRaisesMessage(restore.RestoreError, 'not a backup'):
            restore.extract_dump(path, self.root)


class DatabaseRestoreTests(SimpleTestCase):
    _DB = {'NAME': 'shop', 'HOST': 'db', 'PORT': 5432, 'USER': 'u', 'PASSWORD': 'p'}

    def test_the_backup_replaces_the_whole_schema_in_one_transaction(self):
        # pg_restore --clean drops only what the backup holds: a table a later
        # migration made survived it, and the next migrate failed on that table.
        ok = subprocess.CompletedProcess([], 0, '', '')
        with patch('core.restore.subprocess.run', side_effect=[ok, ok]) as run:
            restore._pg_restore(self._DB, Path('/tmp/r/db.dump'))
        render, load = (c.args[0] for c in run.call_args_list)
        self.assertEqual(
            render,
            ['pg_restore', '--no-owner', '--no-acl', '-f', '/tmp/r/restore.sql', '/tmp/r/db.dump'],
        )
        self.assertEqual(
            load,
            [
                'psql',
                '-X',
                '-q',
                '-v',
                'ON_ERROR_STOP=1',
                '--single-transaction',
                '-h',
                'db',
                '-p',
                '5432',
                '-U',
                'u',
                '-d',
                'shop',
                '-c',
                'DROP SCHEMA public CASCADE',
                '-c',
                'CREATE SCHEMA public',
                '-f',
                '/tmp/r/restore.sql',
            ],
        )
        self.assertEqual(run.call_args_list[1].kwargs['env']['PGPASSWORD'], 'p')

    def test_a_backup_that_cannot_be_read_runs_nothing(self):
        bad = subprocess.CompletedProcess([], 1, '', 'pg_restore: error: input file is too short\n')
        with (
            patch('core.restore.subprocess.run', return_value=bad) as run,
            self.assertRaisesMessage(restore.RestoreError, 'could not be read'),
        ):
            restore._pg_restore(self._DB, Path('/tmp/r/db.dump'))
        self.assertEqual(run.call_count, 1)

    def test_a_failed_load_says_nothing_changed(self):
        ok = subprocess.CompletedProcess([], 0, '', '')
        failed = subprocess.CompletedProcess([], 3, '', 'psql:x:1: ERROR:  boom\n')
        with (
            patch('core.restore.subprocess.run', side_effect=[ok, failed]),
            self.assertRaisesMessage(restore.RestoreError, 'nothing changed'),
        ):
            restore._pg_restore(self._DB, Path('/tmp/r/db.dump'))

    def test_a_sqlite_database_file_is_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, dump = Path(tmp) / 'db.sqlite3', Path(tmp) / 'db.dump'
            db.write_bytes(b'OLD')
            dump.write_bytes(b'NEW')
            with patch('django.db.connections.close_all'):
                restore._sqlite_restore({'NAME': str(db)}, dump)
            self.assertEqual(db.read_bytes(), b'NEW')
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ['db.dump', 'db.sqlite3'])

    def test_an_in_memory_database_is_refused(self):
        with self.assertRaisesMessage(restore.RestoreError, 'in-memory'):
            restore._sqlite_restore(
                {'NAME': 'file:memorydb_default?mode=memory&cache=shared'}, Path('x')
            )

    def test_no_sessions_to_end_on_sqlite(self):
        self.assertEqual(restore.end_other_sessions(), 0)


class ClearCacheTests(SimpleTestCase):
    def test_only_the_cache_s_own_keys_go_when_redis_backs_it(self):
        # The cache shares its Redis database with Celery's queue.
        fake = Mock(spec=['delete_pattern', 'clear'])
        with patch('django.core.cache.cache', fake):
            restore.clear_cache()
        fake.delete_pattern.assert_called_once_with('*')
        fake.clear.assert_not_called()

    def test_a_cache_without_patterns_is_cleared(self):
        fake = Mock(spec=['clear'])
        with patch('django.core.cache.cache', fake):
            restore.clear_cache()
        fake.clear.assert_called_once_with()


class BackUpCurrentTests(_Folder, SimpleTestCase):
    def test_the_current_data_goes_to_its_own_folder_and_nothing_is_pruned_yet(self):
        def fake(command, **kwargs):
            command.archive_path = Path(kwargs['dest']) / BEFORE

        with patch('core.restore.call_command', side_effect=fake) as call:
            self.assertEqual(restore.back_up_current(), BEFORE)
        kwargs = call.call_args.kwargs
        self.assertEqual(kwargs['dest'], str(self.root / 'pre-restore'))
        self.assertGreater(kwargs['keep'], 1000)  # pruning waits for a restore that worked
        self.assertTrue(kwargs['no_media'])
        self.assertEqual(kwargs['label'], 'before-restore')


class RunTests(_Folder, TestCase):
    def setUp(self):
        super().setUp()
        row = StoreSettings.objects.first() or StoreSettings.objects.create()
        row.store_name = 'Test Shop'
        row.save()
        self.archive = _archive(self.root / 'pre-deploy')
        self.calls = Mock()
        for name, target, kwargs in (
            ('backup', 'core.restore.back_up_current', {'return_value': BEFORE}),
            ('end', 'core.restore.end_other_sessions', {'return_value': 2}),
            ('restore', 'core.restore.restore_database', {}),
            ('plan', 'core.deploys.migration_plan', {'return_value': ([], False)}),
        ):
            patcher = patch(target, **kwargs)
            self.calls.attach_mock(patcher.start(), name)
            self.addCleanup(patcher.stop)

    def _restore(self, *extra, confirm='Test Shop'):
        out = io.StringIO()
        call_command('morph_restore', str(self.archive), '--confirm', confirm, *extra, stdout=out)
        return out.getvalue()

    def test_the_current_data_is_saved_first_then_restored_and_recorded(self):
        output = self._restore('--by', 'boss')
        self.assertEqual(
            [c[0] for c in self.calls.mock_calls], ['backup', 'end', 'restore', 'plan']
        )
        last = restore.last()
        self.assertEqual(last['state'], 'done')
        self.assertEqual((last['file'], last['kind'], last['by']), (NAME, 'pre-deploy', 'boss'))
        self.assertEqual(last['pre_restore'], BEFORE)
        self.assertEqual(last['taken_at'], '2026-10-20T01:21:46+00:00')
        self.assertFalse(restore.is_running())
        self.assertIn(f'Restored {NAME}', output)

    def test_the_wrong_name_changes_nothing_and_is_recorded(self):
        with self.assertRaisesMessage(CommandError, 'Test Shop'):
            self._restore(confirm='Other Shop')
        self.assertEqual(self.calls.mock_calls, [])
        self.assertFalse(restore.running_path().exists())
        # Started from the screen, a refusal would otherwise be invisible.
        self.assertEqual(restore.last()['state'], 'refused')
        self.assertIn('Test Shop', restore.last()['error'])

    def test_spaces_around_the_name_are_fine_but_case_counts(self):
        self._restore(confirm='  Test Shop  ')
        self.assertEqual(restore.last()['state'], 'done')
        with self.assertRaises(CommandError):
            self._restore(confirm='test shop')

    def test_no_restore_while_another_runs(self):
        restore.start({'file': 'other'})
        with self.assertRaisesMessage(CommandError, 'Another restore'):
            self._restore()
        self.assertEqual(self.calls.mock_calls, [])
        self.assertTrue(restore.is_running())
        self.assertIsNone(restore.last())  # the running restore's outcome will be the record

    def test_an_archive_without_a_database_never_closes_the_store(self):
        self.archive = _archive(self.root / 'pre-deploy', members={'media.tar': b'm'})
        with self.assertRaisesMessage(CommandError, 'holds no database'):
            self._restore()
        self.assertFalse(restore.running_path().exists())
        self.assertEqual(self.calls.mock_calls, [])

    def test_a_failed_restore_changes_nothing_and_says_so(self):
        self.calls.restore.side_effect = restore.RestoreError(
            'The database could not be restored, so nothing changed: boom'
        )
        with self.assertRaisesMessage(CommandError, 'boom'):
            self._restore()
        self.assertEqual(restore.last()['state'], 'failed')
        self.assertIn('boom', restore.last()['error'])
        self.assertFalse(restore.is_running())

    def test_a_failed_backup_of_the_current_data_stops_the_restore(self):
        self.calls.backup.side_effect = subprocess.CalledProcessError(1, ['pg_dump'])
        with self.assertRaisesMessage(CommandError, 'could not be backed up first'):
            self._restore()
        self.calls.restore.assert_not_called()
        self.assertEqual(restore.last()['state'], 'failed')

    def test_cached_values_are_dropped_after_a_restore(self):
        cache.set('restore-test-key', 'old')
        self._restore()
        self.assertIsNone(cache.get('restore-test-key'))

    def test_a_backup_older_than_the_code_names_what_it_lacks(self):
        self.calls.plan.return_value = (['shop.0002_extra'], False)
        output = self._restore()
        self.assertEqual(restore.last()['missing'], ['shop.0002_extra'])
        self.assertIn('shop.0002_extra', output)
        self.assertIn('Redeploy', output)

    def test_the_web_workers_reload_after_a_restore_started_from_the_page(self):
        with patch('core.restore.os.kill') as kill:
            self._restore('--reload-web', '4242')
        kill.assert_called_once_with(4242, signal.SIGHUP)

    def test_nothing_reloads_after_a_failed_restore(self):
        self.calls.restore.side_effect = restore.RestoreError('nothing changed: boom')
        with patch('core.restore.os.kill') as kill, self.assertRaises(CommandError):
            self._restore('--reload-web', '4242')
        kill.assert_not_called()

    def test_the_store_is_closed_while_the_data_is_replaced(self):
        seen = []
        self.calls.restore.side_effect = lambda dump: seen.append(restore.is_running())
        self._restore()
        self.assertEqual(seen, [True])


class SpawnTests(_Folder, SimpleTestCase):
    def test_the_restore_runs_detached_with_the_page_s_answers(self):
        with patch('core.restore.subprocess.Popen') as popen:
            restore.spawn(self.root / NAME, confirm='Test Shop', by='boss', reload_pid=42)
        argv = popen.call_args.args[0]
        self.assertEqual(
            argv[2:],
            [
                'morph_restore',
                str(self.root / NAME),
                '--confirm',
                'Test Shop',
                '--by',
                'boss',
                '--reload-web',
                '42',
            ],
        )
        self.assertTrue(popen.call_args.kwargs['start_new_session'])
        self.assertTrue((self.root / 'restore' / 'restore.log').exists())


class PreRestoreCopyTests(_Folder, TestCase):
    """The copies of the data restores replaced are an undo: none goes before a
    restore has worked, and never the one being restored."""

    def setUp(self):
        super().setUp()
        row = StoreSettings.objects.first() or StoreSettings.objects.create()
        row.store_name = 'Test Shop'
        row.save()
        self.folder = self.root / 'pre-restore'
        self.old = [
            _archive(self.folder, f'morpheus-backup-20261019T10000{i}Z-before-restore.tar.gz')
            for i in (1, 2, 3)
        ]
        self.made = 0
        patchers = [
            patch('core.restore.PRE_RESTORE_KEEP', 3),
            patch('core.restore.call_command', side_effect=self._fake_backup),
            patch('core.restore.end_other_sessions', return_value=0),
            patch('core.deploys.migration_plan', return_value=([], False)),
        ]
        restore_database = patch('core.restore.restore_database')
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.restore_database = restore_database.start()
        self.addCleanup(restore_database.stop)

    def _fake_backup(self, command, **kwargs):
        """morph_backup, as far as this needs: write the copy, then keep the newest ``keep``."""
        dest = Path(kwargs['dest'])
        self.made += 1
        command.archive_path = _archive(
            dest, f'morpheus-backup-20261021T00000{self.made}Z-before-restore.tar.gz'
        )
        for old in sorted(dest.glob('morpheus-backup-*.tar.gz'), reverse=True)[kwargs['keep'] :]:
            old.unlink()

    def _restore(self, archive):
        with contextlib.suppress(CommandError):
            call_command(
                'morph_restore', str(archive), '--confirm', 'Test Shop', stdout=io.StringIO()
            )

    def _left(self):
        return sorted(p.name for p in self.folder.glob('morpheus-backup-*.tar.gz'))

    def test_restoring_the_oldest_copy_never_deletes_it(self):
        self._restore(self.old[0])
        self.assertTrue(self.old[0].exists())

    def test_a_failed_restore_deletes_no_copy(self):
        self.restore_database.side_effect = restore.RestoreError('nothing changed: boom')
        self._restore(_archive(self.root / 'pre-deploy'))
        self.assertEqual(len(self._left()), 4)

    def test_after_a_restore_that_worked_the_newest_copies_are_kept(self):
        self._restore(_archive(self.root / 'pre-deploy'))
        new = 'morpheus-backup-20261021T000001Z-before-restore.tar.gz'
        self.assertEqual(self._left(), sorted([self.old[1].name, self.old[2].name, new]))


class BackupMigrationsTests(_Folder, SimpleTestCase):
    """Before anything runs, the screen says which migrations a backup lacks."""

    def _sqlite_backup(self, rows):
        path = self.root / 'db.sqlite3'
        with contextlib.closing(sqlite3.connect(path)) as db:
            db.execute(
                'CREATE TABLE django_migrations (id integer primary key, app text, name text, applied text)'
            )
            db.executemany(
                'INSERT INTO django_migrations (app, name, applied) VALUES (?, ?, ?)',
                [(app, name, '2026-10-20') for app, name in rows],
            )
            db.commit()
        return _archive(self.root, members={'db.dump': path.read_bytes()})

    def test_a_sqlite_backup_s_migrations_are_read(self):
        archive = self._sqlite_backup([('core', '0001_initial'), ('shop', '0002_extra')])
        self.assertEqual(
            restore.backup_migrations(archive), {('core', '0001_initial'), ('shop', '0002_extra')}
        )

    def test_a_postgres_backup_s_migrations_are_read_from_its_data(self):
        archive = _archive(self.root, members={'db.dump': b'PGDMP\x01\x0e\x00'})
        copy = (
            'SET statement_timeout = 0;\n'
            'COPY public.django_migrations (id, app, name, applied) FROM stdin;\n'
            '1\tcore\t0001_initial\t2026-06-20 10:00:00+00\n'
            '2\tcore\t0024_deployevent\t2026-10-20 01:21:00+00\n'
            '\\.\n'
        )
        done = subprocess.CompletedProcess([], 0, copy, '')
        with patch('core.restore.subprocess.run', return_value=done) as run:
            self.assertEqual(
                restore.backup_migrations(archive),
                {('core', '0001_initial'), ('core', '0024_deployevent')},
            )
        self.assertEqual(
            run.call_args.args[0][:4],
            ['pg_restore', '--data-only', '--table=django_migrations', '-f'],
        )

    def test_a_backup_whose_migrations_cannot_be_read_gives_none(self):
        self.assertIsNone(
            restore.backup_migrations(_archive(self.root, members={'media.tar': b'm'}))
        )
        self.assertIsNone(
            restore.backup_migrations(_archive(self.root, members={'db.dump': b'neither'}))
        )

    def test_the_running_code_s_missing_migrations_are_named(self):
        from django.db.migrations.loader import MigrationLoader

        graph = MigrationLoader(None, ignore_no_migrations=True).graph
        applied = set(graph.nodes) - {('core', '0024_deployevent')}
        self.assertEqual(restore.missing_for(applied), ['core.0024_deployevent'])
