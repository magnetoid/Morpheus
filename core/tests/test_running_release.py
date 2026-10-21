"""What the store runs, for Settings → Version & updates and Linda (safe deploys, part 5)."""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from core.deploys import latest_predeploy_backup, running_release
from core.models import DeployEvent
from core.updates import can_self_update


class _BackupFolderMixin:
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.folder = self.root / 'pre-deploy'
        env = patch.dict(os.environ, {'MORPHEUS_BACKUP_DIR': tmp.name, 'SOURCE_COMMIT': 'e' * 40})
        env.start()
        self.addCleanup(env.stop)


class CanSelfUpdateTests(SimpleTestCase):
    def test_only_a_git_checkout_can_update_itself(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch('core.updates._repo_root', return_value=Path(tmp)),
            patch('shutil.which', return_value='/usr/bin/git'),
        ):
            self.assertFalse(can_self_update())
            (Path(tmp) / '.git').mkdir()
            self.assertTrue(can_self_update())

    def test_a_checkout_without_git_installed_cannot_update_itself(self):
        # An image built from a clone keeps /app/.git, and the Dockerfile purges git.
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch('core.updates._repo_root', return_value=Path(tmp)),
            patch('shutil.which', return_value=None),
        ):
            (Path(tmp) / '.git').mkdir()
            self.assertFalse(can_self_update())


class LatestBackupTests(_BackupFolderMixin, SimpleTestCase):
    def test_none_when_the_folder_does_not_exist(self):
        self.assertIsNone(latest_predeploy_backup())

    def test_the_newest_backup_with_its_size_time_and_label(self):
        self.folder.mkdir()
        (self.folder / 'morpheus-backup-20261018T090000Z-v0.117.0-aaaaaaa.tar.gz').write_bytes(b'1')
        (self.folder / 'morpheus-backup-20261019T140200Z-v0.118.0-bbbbbbb.tar.gz').write_bytes(
            b'123'
        )
        self.assertEqual(
            latest_predeploy_backup(),
            {
                'name': 'morpheus-backup-20261019T140200Z-v0.118.0-bbbbbbb.tar.gz',
                'size': 3,
                'taken_at': datetime(2026, 10, 19, 14, 2, tzinfo=UTC),
                'label': 'v0.118.0-bbbbbbb',
            },
        )

    def test_files_that_are_not_backups_are_ignored(self):
        self.folder.mkdir()
        (self.folder / 'morpheus-backup-junk.tar.gz').write_bytes(b'x')
        (self.folder / 'notes.txt').write_text('x')
        self.assertIsNone(latest_predeploy_backup())


class RunningReleaseTests(_BackupFolderMixin, TestCase):
    def test_what_runs_and_when_it_was_installed(self):
        when = datetime(2026, 10, 19, 14, 2, tzinfo=UTC)
        DeployEvent.objects.create(
            version=settings.MORPHEUS_VERSION, commit='e' * 40, deployed_at=when
        )
        DeployEvent.objects.create(version='v0.0.1', commit='e' * 40)  # not what runs now
        with patch('core.updates.can_self_update', return_value=False):
            release = running_release()
        self.assertEqual(
            release,
            {
                'version': settings.MORPHEUS_VERSION,
                'commit': 'e' * 40,
                'commit_short': 'eeeeeee',
                'deployed_at': when,
                'backup': None,
                'self_update': False,
                'last_restore': None,
            },
        )

    def test_before_any_record_the_install_time_is_blank(self):
        self.assertIsNone(running_release()['deployed_at'])

    def test_the_last_restore_is_part_of_the_release_record(self):
        folder = self.root / 'restore'
        folder.mkdir()
        (folder / 'last.json').write_text('{"state": "done", "file": "x.tar.gz"}')
        self.assertEqual(running_release()['last_restore'], {'state': 'done', 'file': 'x.tar.gz'})
